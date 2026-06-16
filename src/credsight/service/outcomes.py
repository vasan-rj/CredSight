"""Structured outcomes log for the D2 Learning Loop. Every human decision is recorded
as a DecisionOutcome so the scan() function can detect override patterns."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

_OUTCOMES_FILE = Path("var/outcomes.jsonl")


class DecisionOutcome(BaseModel):
    app_id: str
    ts: str
    segment: str                  # sector / archetype bucket
    model_recommendation: str     # "offer" | "refer"
    human_decision: str           # "approve" | "override" | "request_info"
    override: str | None          # "up" | "down" | None
    reason: str
    model_version: str


def classify_override(model_rec: str, human: str) -> str | None:
    """Classify the direction of an override relative to the model recommendation."""
    if model_rec == "refer" and human == "approve":
        return "up"
    if model_rec == "offer" and human == "override":
        return "down"
    return None


def log_outcome(o: DecisionOutcome) -> None:
    _OUTCOMES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _OUTCOMES_FILE.open("a", encoding="utf-8") as fh:
        fh.write(o.model_dump_json() + "\n")


def query(segment: str | None = None, days: int = 30) -> list[DecisionOutcome]:
    if not _OUTCOMES_FILE.exists():
        return []
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    results: list[DecisionOutcome] = []
    for line in _OUTCOMES_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            o = DecisionOutcome.model_validate_json(line)
            ts = datetime.fromisoformat(o.ts).timestamp()
        except Exception:
            continue
        if ts < cutoff:
            continue
        if segment and o.segment != segment:
            continue
        results.append(o)
    return results
