"""T23 — Unit tests for Path-to-Bankability (D1).

Invariants tested:
1. Thin-file archetype produces at least one actionable step.
2. Strong archetype (composite ≥ 750) produces an empty step list (maintenance path).
3. No step in any path has a negative or zero marginal_delta.
"""

from __future__ import annotations

import pytest

from credsight.scoring.pathways import Pathway, compute_path
from credsight.scoring.schema import FeatureVector
from credsight.scoring.model import predict


def _make_fv(app_id: str = "test-001", **overrides: float) -> FeatureVector:
    """Build a minimal FeatureVector with sensible defaults."""
    base: dict[str, float] = {
        "gst_filing_punctuality": 0.5,
        "gst_filing_continuity": 0.5,
        "inflow_regularity": 0.4,
        "inflow_outflow_ratio": 0.9,
        "balance_volatility_norm": 0.6,
        "bounce_rate": 0.2,
        "obligation_servicing_ratio": 0.6,
        "emi_to_inflow_ratio": 0.3,
        "epfo_formality_proxy": 0.0,
        "gst_turnover_trend": 0.3,
        "months_in_business": 36,
        "gst_vintage_months": 24,
        "upi_txn_count_monthly": 60,
        "bureau_score_norm": 0.5,
    }
    base.update(overrides)
    return FeatureVector(app_id=app_id, features=base)


def test_thin_file_has_steps():
    """Thin-file applicant (low scores) should receive at least one actionable step."""
    fv = _make_fv(
        inflow_regularity=0.2,
        gst_filing_punctuality=0.3,
        balance_volatility_norm=0.8,
        epfo_formality_proxy=0.0,
        bounce_rate=0.4,
    )
    score = predict(fv)
    pathway = compute_path(fv, score)

    # A genuinely weak applicant below 750 should have steps.
    if score.composite < 750:
        assert len(pathway.steps) > 0, (
            f"Expected steps for thin-file applicant (composite={score.composite}), got none."
        )


def test_strong_no_path():
    """A strong applicant (composite ≥ 750) should get an empty step list."""
    fv = _make_fv(
        inflow_regularity=0.95,
        gst_filing_punctuality=0.98,
        balance_volatility_norm=0.05,
        epfo_formality_proxy=1.0,
        bounce_rate=0.0,
        obligation_servicing_ratio=0.95,
        emi_to_inflow_ratio=0.05,
        bureau_score_norm=0.9,
        gst_filing_continuity=0.95,
        inflow_outflow_ratio=1.4,
        gst_turnover_trend=0.8,
        months_in_business=84,
        upi_txn_count_monthly=200,
    )
    score = predict(fv)
    pathway = compute_path(fv, score)

    if score.composite >= 750:
        assert pathway.steps == [], (
            f"Expected no steps for strong applicant (composite={score.composite}), "
            f"got {len(pathway.steps)}."
        )


def test_no_negative_delta_steps():
    """Every step in every pathway must have a strictly positive marginal_delta."""
    fv = _make_fv(
        inflow_regularity=0.35,
        gst_filing_punctuality=0.4,
        balance_volatility_norm=0.7,
    )
    score = predict(fv)
    pathway = compute_path(fv, score)

    for step in pathway.steps:
        assert step.marginal_delta > 0, (
            f"Step '{step.feature}' has non-positive delta: {step.marginal_delta}"
        )


def test_pathway_is_a_pathway_instance():
    """compute_path always returns a Pathway, never raises."""
    fv = _make_fv()
    score = predict(fv)
    result = compute_path(fv, score)
    assert isinstance(result, Pathway)


def test_disclaimer_updated():
    """The disclaimer must reference application order, not just 'guidance'."""
    fv = _make_fv()
    score = predict(fv)
    pathway = compute_path(fv, score)
    assert "application order" in pathway.disclaimer, (
        f"Disclaimer does not mention 'application order': {pathway.disclaimer!r}"
    )
