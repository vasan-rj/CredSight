"""Trained-model composite + real SHAP explainability (ref-doc 04 §Explainability).

Composite = 300 + (1 - calibrated_P(bad)) * 600, so a higher default probability lowers
the credit score. SHAP TreeExplainer attributes the model's margin to each feature; we
flip the sign so a reported positive `shap_value` means the feature SUPPORTS the score
(lowers risk) and negative means it weakens it — the borrower-facing convention.

The Explainability subagent renders these drivers into language, constrained by
governance/faithfulness.py to reference only these actual drivers."""

from __future__ import annotations

import numpy as np

from .artifacts import TrainedModel
from .features import vectorize
from .schema import SCORE_MAX, SCORE_MIN, FeatureVector, ShapDriver

TOP_K = 6


def _composite_from_prob(p_bad: float) -> int:
    score = SCORE_MIN + (1.0 - p_bad) * (SCORE_MAX - SCORE_MIN)
    return int(round(max(SCORE_MIN, min(SCORE_MAX, score))))


def predict_and_explain(tm: TrainedModel, fv: FeatureVector) -> tuple[int, list[ShapDriver]]:
    """Run the trained model + SHAP. Returns (composite_300_900, top-k drivers).

    SHAP uses XGBoost's native exact tree-SHAP (`pred_contribs`) — margin (log-odds)
    contributions toward the 'bad' class, robust across xgboost versions."""
    import xgboost as xgb

    X = vectorize(fv)  # 1xN in FEATURE_ORDER

    raw_p = float(tm.clf.predict_proba(X)[0, 1])      # P(bad), uncalibrated
    p_bad = float(tm.calibrator.predict([raw_p])[0])  # calibrated P(bad)
    composite = _composite_from_prob(p_bad)

    booster = tm.clf.get_booster()
    contribs = booster.predict(xgb.DMatrix(X), pred_contribs=True)[0]
    shap_row = contribs[:-1]  # drop the bias term; remainder is per-feature, positional

    drivers: list[ShapDriver] = []
    for name, raw_val, sv in zip(tm.feature_order, X[0], shap_row):
        score_contrib = -float(sv)  # flip: + => supports the score (lowers risk)
        drivers.append(ShapDriver(
            feature=name,
            value=round(float(raw_val), 4) if not np.isnan(raw_val) else 0.0,
            shap_value=round(score_contrib, 4),
            direction="positive" if score_contrib >= 0 else "negative",
        ))
    drivers.sort(key=lambda d: abs(d.shap_value), reverse=True)
    return composite, drivers[:TOP_K]
