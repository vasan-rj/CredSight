"""Per-dimension sub-scores: transparent, monotonic transforms on each dimension's
features so each sub-score is independently explainable (ref-doc 04 §Modelling approach).

These are deliberately simple and inspectable — a regulator can read them. The XGBoost
composite (model.py) adds ranking power on top; this layer gives interpretability.

TODO (days 3-6): replace placeholder transforms with calibrated ones once the synthetic
feature distributions exist. Keep every transform monotonic and documented.
"""

from __future__ import annotations

from .schema import Dimension, FeatureVector


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def cash_flow_health(f: dict[str, float]) -> float:
    """Inflow regularity, avg balance, volatility, inflow/outflow ratio, seasonality.
    Higher regularity + balance, lower volatility => higher score."""
    regularity = f.get("inflow_regularity", 0.5)  # 1 - coefficient_of_variation, [0,1]
    io_ratio = f.get("inflow_outflow_ratio", 1.0)
    volatility = f.get("balance_volatility_norm", 0.5)  # [0,1], lower better
    raw = 100 * (0.5 * regularity + 0.3 * min(io_ratio, 1.5) / 1.5 + 0.2 * (1 - volatility))
    return _clamp(raw)


def gst_turnover_signal(f: dict[str, float]) -> float:
    """Turnover trend, filing punctuality/continuity, input-tax behaviour."""
    punctuality = f.get("gst_filing_punctuality", 0.5)  # [0,1]
    continuity = f.get("gst_filing_continuity", 0.5)  # months_filed / months_registered
    trend = f.get("gst_turnover_trend", 0.0)  # QoQ growth, can be negative
    raw = 100 * (0.4 * punctuality + 0.4 * continuity + 0.2 * _clamp((trend + 0.2) / 0.4, 0, 1))
    return _clamp(raw)


def banking_discipline(f: dict[str, float]) -> float:
    """Bounces, returns, overdraft behaviour, obligation servicing. Bounces hurt most."""
    bounce_rate = f.get("bounce_rate", 0.0)  # [0,1], lower better
    obligation_servicing = f.get("obligation_servicing_ratio", 1.0)  # paid/due, [0,1]
    raw = 100 * (0.6 * (1 - min(bounce_rate, 1.0)) + 0.4 * min(obligation_servicing, 1.0))
    return _clamp(raw)


def business_vintage_stability(f: dict[str, float]) -> float:
    """GST registration age, filing continuity, operational/address stability."""
    vintage_years = f.get("gst_vintage_years", 0.0)
    stability = f.get("operational_stability", 0.5)  # [0,1]
    raw = 100 * (0.6 * _clamp(vintage_years / 5.0, 0, 1) + 0.4 * stability)
    return _clamp(raw)


def obligation_load_formality(f: dict[str, float]) -> float:
    """Existing EMI load vs inflow, leverage; EPFO as scale/formality proxy.
    Lower leverage => higher score."""
    leverage = f.get("emi_to_inflow_ratio", 0.0)  # lower better
    formality = f.get("epfo_formality_proxy", 0.0)  # [0,1], having employees helps
    raw = 100 * (0.7 * (1 - min(leverage, 1.0)) + 0.3 * formality)
    return _clamp(raw)


_DISPATCH = {
    Dimension.CASH_FLOW: cash_flow_health,
    Dimension.GST_TURNOVER: gst_turnover_signal,
    Dimension.BANKING_DISCIPLINE: banking_discipline,
    Dimension.VINTAGE_STABILITY: business_vintage_stability,
    Dimension.OBLIGATION_LOAD: obligation_load_formality,
}


def compute_dimensions(fv: FeatureVector) -> dict[Dimension, float]:
    """Compute all five 0-100 sub-scores from a feature vector."""
    return {dim: fn(fv.features) for dim, fn in _DISPATCH.items()}
