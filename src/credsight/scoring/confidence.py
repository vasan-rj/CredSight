"""Thin-file confidence ∈ [0,1] (FR-11, ref-doc 04). Travels with every score; low
confidence routes a case to the HITL gate. This is a differentiator: we present a score
AND how much to trust it, instead of false precision.

Confidence rises with: number of sources present, months of history, cross-source
agreement. Deterministic — no model, no LLM."""

from __future__ import annotations

from .schema import FeatureVector

MAX_SOURCES = 5  # bank, gst, upi, epfo, bureau
TARGET_MONTHS = 12


def compute_confidence(fv: FeatureVector) -> float:
    source_score = min(fv.n_sources / MAX_SOURCES, 1.0)
    history_score = min(fv.months_history / TARGET_MONTHS, 1.0)
    agreement_score = max(0.0, min(fv.cross_source_agreement, 1.0))
    # Weighted: agreement matters most (a disagreement is a real red flag), then breadth,
    # then depth of history.
    conf = 0.4 * agreement_score + 0.35 * source_score + 0.25 * history_score
    return round(conf, 3)
