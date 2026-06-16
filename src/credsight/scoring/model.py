"""The versioned composite model + the scoring service entrypoint (`predict`).

Composite = calibrated XGBoost over dimension features for ranking power, plus the
weighted-dimension view for interpretability. Both are shown (ref-doc 04).

Until a trained model artifact exists, `predict` falls back to the deterministic
weighted-dimension composite so the whole pipeline + demo work end-to-end from day one.
Swap in the trained XGBoost (days 3-6) without changing the `predict` signature — that
signature IS the `score_model.predict` MCP contract.

THE LLM NEVER CALLS INTO HERE TO PRODUCE A NUMBER.
"""

from __future__ import annotations

from . import artifacts
from ..config import config
from .confidence import compute_confidence
from .dimensions import compute_dimensions
from .schema import (
    DIMENSION_WEIGHTS,
    SCORE_MAX,
    SCORE_MIN,
    FeatureVector,
    ScoreResult,
    ShapDriver,
)


def _weighted_composite(dimensions: dict) -> int:
    """Interpretable fallback composite: weighted dimension average mapped to 300-900."""
    weighted_0_100 = sum(DIMENSION_WEIGHTS[d] * v for d, v in dimensions.items())
    scaled = SCORE_MIN + (weighted_0_100 / 100.0) * (SCORE_MAX - SCORE_MIN)
    return int(round(scaled))


def predict(fv: FeatureVector) -> ScoreResult:
    """Deterministic, versioned scoring. The `score_model.predict` MCP tool wraps this.

    Returns dimensions (0-100 each), a 300-900 composite, thin-file confidence, and SHAP
    drivers. Same input always yields the same output.

    When a trained artifact exists (run `credsight-train`), the composite + SHAP come from
    the calibrated XGBoost model; otherwise it falls back to the interpretable
    weighted-dimension composite so the pipeline works end-to-end without training."""
    dimensions = compute_dimensions(fv)
    confidence = compute_confidence(fv)

    trained = artifacts.load(config.score_model_version)
    if trained is None:
        composite = _weighted_composite(dimensions)
        shap_drivers = _dimension_pseudo_shap(dimensions)
    else:
        composite, shap_drivers = _predict_with_model(trained, fv)

    return ScoreResult(
        app_id=fv.app_id,
        model_version=config.score_model_version,
        dimensions=dimensions,
        composite=composite,
        confidence=confidence,
        shap=shap_drivers,
    )


def _dimension_pseudo_shap(dimensions: dict) -> list[ShapDriver]:
    """Fallback explanation when no trained model: weighted dimension contributions
    relative to a neutral 50 baseline. Replaced by true SHAP (explain.py) once trained."""
    drivers = []
    for dim, val in dimensions.items():
        contribution = DIMENSION_WEIGHTS[dim] * (val - 50.0)
        drivers.append(
            ShapDriver(
                feature=dim.value,
                value=round(val, 2),
                shap_value=round(contribution, 3),
                direction="positive" if contribution >= 0 else "negative",
            )
        )
    drivers.sort(key=lambda d: abs(d.shap_value), reverse=True)
    return drivers


def _predict_with_model(trained, fv: FeatureVector):
    """Run the trained XGBoost composite + real SHAP."""
    from . import explain  # local import: shap loaded only when a trained model is present

    return explain.predict_and_explain(trained, fv)
