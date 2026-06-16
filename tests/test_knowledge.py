"""GBrain knowledge brain: hybrid search over seeded policy Markdown, incremental
indexing, and capture-then-searchable (the read-and-write loop)."""

from __future__ import annotations

from pathlib import Path

from credsight.knowledge import brain
from credsight.knowledge.index import LexicalIndex


def test_search_finds_working_capital_policy():
    clauses = brain.search("unsecured working capital limit by score band")
    assert clauses, "expected at least one clause"
    assert clauses[0].source == "working-capital-eligibility"
    assert clauses[0].ref.startswith("working-capital-eligibility#")


def test_search_routes_fraud_query_to_fraud_doc():
    clauses = brain.search("circular UPI reversals gaming pre-application inflow spike")
    assert clauses
    assert clauses[0].source == "fraud-and-consent"


def test_search_empty_for_irrelevant_query():
    assert brain.search("photosynthesis chlorophyll astronomy") == []


def test_incremental_index_picks_up_new_doc(tmp_path):
    idx = LexicalIndex([tmp_path])
    (tmp_path / "a.md").write_text("# A\n\n## Alpha clause\nworking capital eligibility limit\n")
    idx.refresh()
    assert idx.search("working capital eligibility")[0].source == "a"

    # Add a second doc; refresh reprocesses only the new file and it becomes searchable.
    (tmp_path / "b.md").write_text("# B\n\n## Beta clause\ncircular upi fraud reversal signal\n")
    res = idx.search("circular upi fraud")
    assert res and res[0].source == "b"


def test_capture_then_searchable():
    note = "Observed circular UPI ring among three VPAs in a textiles cluster; flag."
    try:
        assert brain.capture(note, tags=["fraud", "textiles"]) is True
        hits = brain.search("textiles cluster circular UPI ring")
        assert any("captured-learnings" in c.source or "textiles" in c.text.lower() for c in hits)
    finally:
        # Clean up the runtime-written learnings file so the test is idempotent.
        f = Path(brain.__file__).parent / "learned" / "captured-learnings.md"
        if f.exists():
            f.unlink()
        brain._INDEX.refresh()
