"""I/O contracts for the scoring core. Mirrors the `score_model.predict` MCP tool
(ref-doc 05): in = features, out = {dimensions, composite, shap, confidence}."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Dimension(str, Enum):
    CASH_FLOW = "cash_flow_health"
    GST_TURNOVER = "gst_turnover_signal"
    BANKING_DISCIPLINE = "banking_discipline"
    VINTAGE_STABILITY = "business_vintage_stability"
    OBLIGATION_LOAD = "obligation_load_formality"


# Defensible starting weights — exposed as config, calibrated against synthetic labels.
# Any change must be documented (auditability, ref-doc 04).
DIMENSION_WEIGHTS: dict[Dimension, float] = {
    Dimension.CASH_FLOW: 0.30,
    Dimension.GST_TURNOVER: 0.20,
    Dimension.BANKING_DISCIPLINE: 0.20,
    Dimension.VINTAGE_STABILITY: 0.15,
    Dimension.OBLIGATION_LOAD: 0.15,
}

# Composite is scaled to the familiar 300-900 band.
SCORE_MIN, SCORE_MAX = 300, 900


class FeatureVector(BaseModel):
    """Derived by the Reconciliation subagent, written to features/{app_id}.json.
    Keys are stable feature names; values numeric. Kept generic so the pipeline can
    grow without breaking the model contract."""

    app_id: str
    features: dict[str, float] = Field(default_factory=dict)
    # Inputs for the thin-file confidence computation.
    n_sources: int = 0
    months_history: int = 0
    cross_source_agreement: float = 1.0  # [0,1]


class ShapDriver(BaseModel):
    feature: str
    value: float
    shap_value: float  # signed contribution
    direction: str  # "positive" | "negative"


class ScoreResult(BaseModel):
    app_id: str
    model_version: str
    dimensions: dict[Dimension, float]  # each 0-100
    composite: int  # 300-900
    confidence: float  # [0,1] — thin-file honesty (FR-11)
    shap: list[ShapDriver] = Field(default_factory=list)
