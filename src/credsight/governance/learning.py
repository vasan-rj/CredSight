"""Learning Loop D2.2 — detect override patterns from the outcomes log and propose
versioned recalibration to the risk team. Never mutates the model; all recommendations
require human approval before any config change. 'Learns' ≠ 'drifts'."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from ..knowledge.brain import capture
from ..service.outcomes import DecisionOutcome, query

# Canonical threshold — how many same-direction overrides in a segment before the
# system surfaces a recalibration recommendation for human review.
PATTERN_THRESHOLD = 8

# Guard set: prevents duplicate GBrain capture() calls on repeated API polls within
# the same process lifetime. rec_id is window-scoped (includes date) so a new 30-day
# window naturally gets a fresh entry.
_emitted_rec_ids: set[str] = set()


class RecalRecommendation(BaseModel):
    id: str
    segment: str
    pattern: str
    suggestion: str
    evidence_count: int
    status: str = "pending_human_approval"


def scan(window_days: int = 30, threshold: int = PATTERN_THRESHOLD) -> list[RecalRecommendation]:
    """Scan the outcomes log; emit a RecalRecommendation for each (segment, direction)
    pair whose override count reaches the threshold. Writes captured learnings to
    GBrain so the knowledge graph self-wires the pattern."""
    outcomes = query(days=window_days)
    window_start_date = (datetime.now(timezone.utc) - timedelta(days=window_days)).strftime("%Y%m%d")
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
            id=f"rec-{segment}-{direction}-{window_start_date}",
            segment=segment, pattern=pattern,
            suggestion=suggestion, evidence_count=n,
        )
        recs.append(rec)
        if rec.id not in _emitted_rec_ids:
            capture(f"{pattern} → {suggestion}", tags=["learned-pattern", segment, direction])
            _emitted_rec_ids.add(rec.id)
    return recs
