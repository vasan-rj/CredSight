"""Learning Loop D2.2 — detect override patterns from the outcomes log and propose
versioned recalibration to the risk team. Never mutates the model; all recommendations
require human approval before any config change. 'Learns' ≠ 'drifts'."""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel

from ..knowledge.brain import capture
from ..service.outcomes import DecisionOutcome, query


class RecalRecommendation(BaseModel):
    id: str
    segment: str
    pattern: str
    suggestion: str
    evidence_count: int
    status: str = "pending_human_approval"


def scan(window_days: int = 30, threshold: int = 5) -> list[RecalRecommendation]:
    """Scan the outcomes log; emit a RecalRecommendation for each (segment, direction)
    pair whose override count reaches the threshold. Writes captured learnings to
    GBrain so the knowledge graph self-wires the pattern."""
    outcomes = query(days=window_days)
    by_seg_dir: dict[tuple[str, str], list[DecisionOutcome]] = defaultdict(list)
    for o in outcomes:
        if o.override:
            by_seg_dir[(o.segment, o.override)].append(o)

    recs: list[RecalRecommendation] = []
    for (segment, direction), items in by_seg_dir.items():
        if len(items) < threshold:
            continue
        n, w = len(items), window_days
        if direction == "up":
            pattern = f"{n} {segment} cases approved despite model 'refer' in {w}d"
            suggestion = f"Raise HITL floor or increase cash_flow weight for {segment}"
        else:
            pattern = f"{n} {segment} cases rejected despite model 'offer' in {w}d"
            suggestion = f"Tighten policy threshold or lower offer amount for {segment}"
        rec = RecalRecommendation(
            id=f"rec-{segment}-{direction}",
            segment=segment, pattern=pattern,
            suggestion=suggestion, evidence_count=n,
        )
        recs.append(rec)
        # Write-back to GBrain — the dream cycle will wire this into the knowledge graph.
        capture(f"{pattern} → {suggestion}", tags=["learned-pattern", segment, direction])
    return recs
