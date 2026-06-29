"""T24 — Unit tests for Learning Loop D2 (outcomes, scan, PATTERN_THRESHOLD).

Invariants tested:
1. classify_override correctly maps all 6 (model_rec, human_decision) pairs.
2. scan() returns nothing below PATTERN_THRESHOLD, returns recs at/above it.
3. PATTERN_THRESHOLD is exactly 8 (canonical constant, guards demo narrative).
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from credsight.governance.learning import PATTERN_THRESHOLD, RecalRecommendation, scan
from credsight.service.outcomes import DecisionOutcome, classify_override


# ── classify_override ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("model_rec,human,expected", [
    ("refer",  "approve",      "up"),
    ("offer",  "override",     "down"),
    ("refer",  "override",     None),   # not an override
    ("offer",  "approve",      None),   # already offered → approve is concordant
    ("refer",  "request_info", None),
    ("offer",  "request_info", None),
])
def test_classify_override(model_rec: str, human: str, expected: str | None):
    result = classify_override(model_rec, human)
    assert result == expected, (
        f"classify_override({model_rec!r}, {human!r}) = {result!r}, expected {expected!r}"
    )


# ── PATTERN_THRESHOLD ─────────────────────────────────────────────────────────

def test_pattern_threshold_is_eight():
    """Canonical constant must be 8 — matches plan doc and demo narrative."""
    assert PATTERN_THRESHOLD == 8, (
        f"PATTERN_THRESHOLD is {PATTERN_THRESHOLD}, expected 8. "
        "This constant controls the override-to-recommendation gate. "
        "Changing it without updating the plan doc breaks the demo narrative."
    )


# ── scan() threshold behaviour ────────────────────────────────────────────────

def _make_outcome(segment: str, model_rec: str, human: str, n: int) -> list[DecisionOutcome]:
    override = classify_override(model_rec, human)
    ts = datetime.now(timezone.utc).isoformat()
    return [
        DecisionOutcome(
            app_id=f"app-{i}",
            ts=ts,
            segment=segment,
            model_recommendation=model_rec,
            human_decision=human,
            override=override,
            reason="test",
            model_version="v0",
        )
        for i in range(n)
    ]


def _write_outcomes(path: Path, outcomes: list[DecisionOutcome]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for o in outcomes:
            fh.write(o.model_dump_json() + "\n")


def test_scan_below_threshold_returns_empty():
    """Below PATTERN_THRESHOLD overrides → no recommendation surfaced."""
    outcomes = _make_outcome("Kirana/retail", "refer", "approve", PATTERN_THRESHOLD - 1)
    with tempfile.TemporaryDirectory() as td:
        outcomes_file = Path(td) / "outcomes.jsonl"
        _write_outcomes(outcomes_file, outcomes)
        with patch("credsight.service.outcomes._OUTCOMES_FILE", outcomes_file):
            recs = scan()
    assert recs == [], (
        f"Expected no recs for {PATTERN_THRESHOLD - 1} overrides "
        f"(threshold={PATTERN_THRESHOLD}), got {len(recs)}."
    )


def test_scan_at_threshold_returns_rec():
    """Exactly PATTERN_THRESHOLD overrides → one recommendation surfaced."""
    outcomes = _make_outcome("Kirana/retail", "refer", "approve", PATTERN_THRESHOLD)
    with tempfile.TemporaryDirectory() as td:
        outcomes_file = Path(td) / "outcomes.jsonl"
        _write_outcomes(outcomes_file, outcomes)
        with patch("credsight.service.outcomes._OUTCOMES_FILE", outcomes_file), \
             patch("credsight.governance.learning.capture") as mock_capture:
            recs = scan()
    assert len(recs) == 1, (
        f"Expected 1 rec for {PATTERN_THRESHOLD} overrides, got {len(recs)}."
    )
    rec = recs[0]
    assert isinstance(rec, RecalRecommendation)
    assert rec.segment == "Kirana/retail"
    assert rec.evidence_count == PATTERN_THRESHOLD
    assert rec.status == "pending_human_approval"


def test_scan_rec_id_includes_date():
    """rec_id must include a date suffix to prevent cross-window collisions."""
    outcomes = _make_outcome("Services", "offer", "override", PATTERN_THRESHOLD)
    with tempfile.TemporaryDirectory() as td:
        outcomes_file = Path(td) / "outcomes.jsonl"
        _write_outcomes(outcomes_file, outcomes)
        with patch("credsight.service.outcomes._OUTCOMES_FILE", outcomes_file), \
             patch("credsight.governance.learning.capture"):
            recs = scan()
    assert len(recs) == 1
    # rec_id format: rec-{segment}-{direction}-{YYYYMMDD}
    parts = recs[0].id.split("-")
    assert len(parts) >= 4, f"rec_id missing date suffix: {recs[0].id!r}"
    date_part = parts[-1]
    assert len(date_part) == 8 and date_part.isdigit(), (
        f"Expected 8-digit date in rec_id, got: {date_part!r}"
    )


def test_scan_capture_not_duplicated(monkeypatch):
    """capture() must not be called twice for the same rec_id in the same process."""
    import credsight.governance.learning as learning_mod

    outcomes = _make_outcome("Wholesale", "refer", "approve", PATTERN_THRESHOLD)
    with tempfile.TemporaryDirectory() as td:
        outcomes_file = Path(td) / "outcomes.jsonl"
        _write_outcomes(outcomes_file, outcomes)

        captured: list[str] = []

        def fake_capture(note: str, tags: list[str] | None = None) -> bool:
            captured.append(note)
            return True

        # Clear the guard set to ensure a clean test.
        learning_mod._emitted_rec_ids.clear()

        with patch("credsight.service.outcomes._OUTCOMES_FILE", outcomes_file):
            monkeypatch.setattr(learning_mod, "capture", fake_capture)
            scan()
            scan()  # second scan in same process lifetime

    assert len(captured) == 1, (
        f"capture() called {len(captured)} times for the same pattern, expected 1."
    )
