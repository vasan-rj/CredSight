"""The fixed feature column order — the contract between the feature pipeline, the trained
model, and SHAP. NEVER reorder this list without retraining and bumping the model version
(reproducibility, ref-doc 04). Missing features are passed as NaN; XGBoost handles them
natively, so a thin file with absent sources still scores."""

from __future__ import annotations

import numpy as np

from .schema import FeatureVector

FEATURE_ORDER: list[str] = [
    "inflow_regularity",
    "inflow_outflow_ratio",
    "balance_volatility_norm",
    "gst_filing_punctuality",
    "gst_filing_continuity",
    "gst_turnover_trend",
    "bounce_rate",
    "obligation_servicing_ratio",
    "gst_vintage_years",
    "operational_stability",
    "emi_to_inflow_ratio",
    "epfo_formality_proxy",
]


def vectorize(fv: FeatureVector) -> np.ndarray:
    """FeatureVector -> 1xN float matrix in FEATURE_ORDER (missing -> NaN)."""
    row = [fv.features.get(k, np.nan) for k in FEATURE_ORDER]
    return np.asarray([row], dtype=float)
