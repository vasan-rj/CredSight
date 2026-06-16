"""Train the calibrated XGBoost composite over synthetic, feature-pipeline-derived data.

Pipeline: generate many MSME bundles across archetypes -> ingest -> reconcile to the same
12 features used at inference -> a transparent 'teacher' risk function assigns each sample
a default probability from credit intuition -> draw Bernoulli labels -> fit XGBoost ->
isotonic-calibrate P(bad) -> persist (clf + calibrator + feature order).

Why a teacher: on synthetic data there are no real outcomes. The teacher encodes credit
intuition (bounces/leverage/declining-turnover raise risk; punctual filing/regular inflow
/growth lower it); the model learns to recover graded risk from features, and SHAP then
explains real, non-degenerate drivers. We do NOT claim a magic accuracy number — we report
ranking + calibration on synthetic archetypes and back-test on sandbox data later
(ref-doc 04 §What to claim).

Fraud samples are INCLUDED and scored on their (gamed, good-looking) features — the
composite trusts them; the separate reconciliation fraud rules are what catch them.

CLI: `credsight-train`."""

from __future__ import annotations

import argparse
import math
import random
import sys

import numpy as np

from ..config import config
from ..data.generators.archetypes import Archetype
from ..data.generators.generate import generate_bundle
from ..data.ingest import build_canonical
from ..reconciliation.reconcile import reconcile
from . import artifacts
from .features import FEATURE_ORDER, vectorize
from .schema import FeatureVector

# Teacher weights: contribution to the risk log-odds. Sign = credit intuition.
_TEACHER = {
    "bounce_rate": 3.0,
    "emi_to_inflow_ratio": 2.5,
    "balance_volatility_norm": 1.0,
    "gst_filing_punctuality": -2.0,
    "inflow_regularity": -1.5,
    "gst_turnover_trend": -3.0,
    "gst_filing_continuity": -1.0,
    "operational_stability": -0.8,
    "epfo_formality_proxy": -0.5,
    "inflow_outflow_ratio": -0.7,
}
# Bias tuned so the synthetic positive (bad) rate lands ~0.2-0.35 (non-degenerate
# calibration + a usable score spread), not a near-empty positive class.
_TEACHER_BIAS = 2.6


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _teacher_risk(features: dict, rng: random.Random) -> float:
    logit = _TEACHER_BIAS
    for k, w in _TEACHER.items():
        v = features.get(k)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            logit += w * v
    logit += -0.3 * min(features.get("gst_vintage_years", 0.0) or 0.0, 10.0)
    logit += rng.gauss(0, 0.4)  # irreducible noise so labels aren't perfectly separable
    return _sigmoid(logit)


def _build_dataset(n_per_archetype: int, seed: int):
    rng = random.Random(seed)
    X, y = [], []
    for a_idx, arch in enumerate(Archetype):
        for i in range(n_per_archetype):
            s = seed + a_idx * 1_000_000 + i  # deterministic per-sample seed
            bundle = generate_bundle(f"TR-{arch.value}-{i}", "train", arch, s)
            cp = build_canonical(bundle["msme_id"], bundle)
            fv, _ = reconcile(cp)
            X.append([fv.features.get(k, np.nan) for k in FEATURE_ORDER])
            risk = _teacher_risk(fv.features, rng)
            y.append(1 if rng.random() < risk else 0)
    return np.asarray(X, dtype=float), np.asarray(y, dtype=int)


def _ks(y_true: np.ndarray, p: np.ndarray) -> float:
    order = np.argsort(p)
    y = y_true[order]
    pos, neg = y.sum(), len(y) - y.sum()
    if pos == 0 or neg == 0:
        return 0.0
    tpr = np.cumsum(y) / pos
    fpr = np.cumsum(1 - y) / neg
    return float(np.max(np.abs(tpr - fpr)))


def train(n_per_archetype: int = 250, seed: int = 42, version: str | None = None,
          base=None) -> dict:
    from sklearn.isotonic import IsotonicRegression
    from sklearn.metrics import brier_score_loss, roc_auc_score
    from sklearn.model_selection import train_test_split
    from xgboost import XGBClassifier

    version = version or config.score_model_version
    X, y = _build_dataset(n_per_archetype, seed)

    X_tr, X_tmp, y_tr, y_tmp = train_test_split(X, y, test_size=0.4, random_state=seed,
                                                stratify=y)
    X_cal, X_te, y_cal, y_te = train_test_split(X_tmp, y_tmp, test_size=0.5,
                                                random_state=seed, stratify=y_tmp)

    clf = XGBClassifier(
        n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.9,
        colsample_bytree=0.9, eval_metric="logloss", missing=np.nan, random_state=seed,
    )
    clf.fit(X_tr, y_tr)

    # Isotonic calibration of P(bad) on the held-out calibration split.
    p_cal = clf.predict_proba(X_cal)[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(p_cal, y_cal)

    # Metrics on the untouched test split.
    p_te_raw = clf.predict_proba(X_te)[:, 1]
    p_te = calibrator.predict(p_te_raw)
    metrics = {
        "n_samples": int(len(y)),
        "test_auc": round(float(roc_auc_score(y_te, p_te)), 4),
        "test_ks": round(_ks(y_te, p_te), 4),
        "test_brier": round(float(brier_score_loss(y_te, p_te)), 4),
        "positive_rate": round(float(y.mean()), 4),
    }

    tm = artifacts.TrainedModel(clf=clf, calibrator=calibrator,
                                feature_order=FEATURE_ORDER, version=version)
    saved = artifacts.save(tm, base=base)
    metrics["artifact"] = str(saved)
    return metrics


def _archetype_composites() -> dict:
    """Composite for each archetype under the freshly trained model (sanity / demo)."""
    from .model import predict

    out = {}
    for arch in Archetype:
        b = generate_bundle(f"SANITY-{arch.value}", "s", arch, seed=777)
        cp = build_canonical(b["msme_id"], b)
        fv, _ = reconcile(cp)
        out[arch.value] = predict(fv).composite
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Train the calibrated XGBoost composite.")
    ap.add_argument("--n", type=int, default=250, help="samples per archetype")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    metrics = train(args.n, args.seed)
    print("Training complete:")
    for k, v in metrics.items():
        print(f"  {k:16s}: {v}")
    print("Archetype composites (trained model):")
    for k, v in _archetype_composites().items():
        print(f"  {k:10s}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# Convenience for ad-hoc use.
def score(fv: FeatureVector):  # pragma: no cover
    from .model import predict

    return predict(fv)
