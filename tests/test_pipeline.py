"""Tests for the full data chain: generate -> ingest -> reconcile -> score.

These lock in the substance: generators produce coherent data, the feature pipeline
recovers the 12 model features, fraud is caught, and archetype ranking holds."""

from __future__ import annotations

import pytest

from credsight.data.generators.archetypes import Archetype
from credsight.data.generators.generate import generate_bundle
from credsight.data.ingest import build_canonical
from credsight.reconciliation.reconcile import reconcile
from credsight.reconciliation.rules import Severity
from credsight.scoring.model import predict
from credsight.scoring.schema import SCORE_MAX, SCORE_MIN

REQUIRED_FEATURES = {
    "inflow_regularity", "inflow_outflow_ratio", "balance_volatility_norm",
    "gst_filing_punctuality", "gst_filing_continuity", "gst_turnover_trend",
    "bounce_rate", "obligation_servicing_ratio",
    "gst_vintage_years", "operational_stability",
    "emi_to_inflow_ratio", "epfo_formality_proxy",
}


def _run(arch: Archetype, seed: int = 900):
    bundle = generate_bundle(f"T-{arch.value}", f"Test {arch.value}", arch, seed)
    cp = build_canonical(bundle["msme_id"], bundle)
    fv, flags = reconcile(cp)
    return fv, flags, predict(fv)


@pytest.mark.parametrize("arch", list(Archetype))
def test_chain_produces_all_features(arch):
    fv, _, score = _run(arch)
    assert REQUIRED_FEATURES.issubset(fv.features.keys())
    assert SCORE_MIN <= score.composite <= SCORE_MAX
    for v in fv.features.values():
        assert v == v  # not NaN


def test_generation_is_reproducible():
    a = _run(Archetype.STRONG, seed=7)
    b = _run(Archetype.STRONG, seed=7)
    assert a[2].composite == b[2].composite
    assert a[0].features == b[0].features


def test_ranking_strong_beats_stressed():
    strong = _run(Archetype.STRONG)[2].composite
    stressed = _run(Archetype.STRESSED)[2].composite
    assert strong > stressed


def test_fraud_archetype_is_flagged():
    _, flags, _ = _run(Archetype.FRAUD)
    codes = {f.code for f in flags}
    assert "CIRCULAR_UPI" in codes
    assert "INFLOW_SPIKE" in codes
    assert any(f.severity == Severity.FRAUD for f in flags)


def test_clean_archetype_has_no_fraud_flag():
    _, flags, _ = _run(Archetype.STRONG)
    assert not any(f.severity == Severity.FRAUD for f in flags)


def test_strong_filing_continuity_is_high():
    # Regression for the window bug: a long-vintage business with full history should
    # read as continuous, not 0.25.
    fv, _, _ = _run(Archetype.STRONG)
    assert fv.features["gst_filing_continuity"] > 0.8
