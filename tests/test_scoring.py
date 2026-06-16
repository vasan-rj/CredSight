"""Smoke + regression tests for the deterministic core. These run today (no trained model,
no LLM, no network) and lock in the invariants. Expand into the 3 fixed archetype
regression cases (thin-file, strong, stressed) as generators land (ref-doc 04 §Eval)."""

from __future__ import annotations

from credsight.scoring.confidence import compute_confidence
from credsight.scoring.dimensions import compute_dimensions
from credsight.scoring.model import _weighted_composite, predict
from credsight.scoring.policy import recommend
from credsight.scoring.schema import SCORE_MAX, SCORE_MIN, Dimension, FeatureVector


def _fv(**kw) -> FeatureVector:
    base = dict(app_id="APP1", features={}, n_sources=3, months_history=12,
                cross_source_agreement=1.0)
    base.update(kw)
    return FeatureVector(**base)


def test_composite_in_band():
    res = predict(_fv())
    assert SCORE_MIN <= res.composite <= SCORE_MAX
    assert set(res.dimensions.keys()) == set(Dimension)


def test_deterministic():
    # Same input -> same output, always (the core invariant).
    a = predict(_fv())
    b = predict(_fv())
    assert a.composite == b.composite
    assert a.dimensions == b.dimensions


def test_confidence_rises_with_evidence():
    thin = compute_confidence(_fv(n_sources=1, months_history=2, cross_source_agreement=0.6))
    rich = compute_confidence(_fv(n_sources=5, months_history=12, cross_source_agreement=1.0))
    assert 0.0 <= thin <= rich <= 1.0
    assert rich > thin


def test_strong_features_beat_empty_interpretable():
    # The interpretable dimension/weighted view (always present, backend-independent):
    # a strong applicant must out-score a no-data applicant.
    strong = _fv(features={
        "inflow_regularity": 0.95, "inflow_outflow_ratio": 1.3, "balance_volatility_norm": 0.1,
        "gst_filing_punctuality": 0.98, "gst_filing_continuity": 1.0, "gst_turnover_trend": 0.1,
        "bounce_rate": 0.0, "obligation_servicing_ratio": 1.0,
        "gst_vintage_years": 5, "operational_stability": 0.9,
        "emi_to_inflow_ratio": 0.1, "epfo_formality_proxy": 0.8,
    })
    assert _weighted_composite(compute_dimensions(strong)) > \
        _weighted_composite(compute_dimensions(_fv()))


def test_recommendation_never_executes():
    rec = recommend(predict(_fv()))
    # A recommendation is data, not an action. It carries policy refs for the audit trail.
    assert hasattr(rec, "eligible")
    assert rec.policy_clause_refs == []
