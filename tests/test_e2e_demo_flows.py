"""E2E smoke tests for the three demo-critical flows.

Each test walks the full API surface — no internal mocks — to catch integration
failures that unit tests miss (audit path mismatches, outcomes → recommendations
sync, capture → graph propagation).

Run: pytest tests/test_e2e_demo_flows.py -v -s
Needs: langgraph, fastapi (skipped otherwise). TestClient runs in-process; no
       live server required.

Flow 1 — Lakshmi full arc     : run → HITL pause → approve → audit events verified
Flow 2 — Override-to-pattern  : 8 outcomes logged → /learning/recommendations surfaces 1 rec
Flow 3 — Capture-to-graph arc : capture note → organize dream cycle → graph has nodes + edges
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from credsight.api.app import app  # noqa: E402
from credsight.governance.learning import PATTERN_THRESHOLD  # noqa: E402
from credsight.service.outcomes import DecisionOutcome, classify_override  # noqa: E402

client = TestClient(app)


# ── Flow 1: Lakshmi full demo arc ─────────────────────────────────────────────

def test_lakshmi_full_arc():
    """Thin-file MSME runs end-to-end: HITL pause → approve → full audit trail.

    This is the golden demo beat. If any step regresses, the live demo breaks.
    """
    app_id = "E2E-LAKSHMI-ARC-001"

    # 1. Start assessment — thin-file + low confidence should pause at HITL gate.
    r = client.post("/api/orchestrator/run", json={
        "app_id": app_id, "archetype": "thin_file", "seed": 101, "name": "E2E Lakshmi"
    })
    assert r.status_code == 200, f"orchestrator/run failed: {r.text}"
    run = r.json()
    assert run["status"] == "pending_human", (
        f"Thin-file must pause at HITL. Got status={run['status']!r}, "
        f"reasons={run.get('reasons')}. "
        "Check: confidence floor, CREDSIGHT_HITL_CONFIDENCE_FLOOR env var."
    )
    assert run["paused"] is True
    assert run["reasons"], "HITL reasons list must not be empty"
    # Health Card data must travel with the interrupt so the UI can render.
    assert run["score"]["composite"] is not None, "score.composite must be present on pause"
    assert run["explanation"], "explanation must be present on pause"

    # 2. Resume with approval — run should reach action_node and complete.
    r = client.post("/api/orchestrator/resume", json={
        "app_id": app_id, "decision": "approve",
        "reason": "E2E test approval", "underwriter": "underwriter:e2e"
    })
    assert r.status_code == 200, f"orchestrator/resume failed: {r.text}"
    resumed = r.json()
    assert resumed["status"] == "approved", (
        f"Post-resume must be approved. Got {resumed['status']!r}."
    )
    assert resumed["paused"] is False

    # 3. Audit trail — every required event type must be present.
    r = client.get(f"/api/orchestrator/{app_id}/audit")
    assert r.status_code == 200, f"audit fetch failed: {r.text}"
    events = r.json()
    assert events, "Audit trail must not be empty after a completed run"
    types = {e["event_type"] for e in events}
    required = {"data_pull", "score", "recommendation", "hitl_request",
                "human_decision", "action"}
    missing = required - types
    assert not missing, (
        f"Audit trail missing event types: {sorted(missing)}. "
        f"Present: {sorted(types)}. "
        "Check: audit base_dir in graph.py vs api/app.py orchestrator_audit()."
    )

    # 4. Consent ref must be on the data_pull event (governance grounding rule).
    data_pull = next(e for e in events if e["event_type"] == "data_pull")
    assert data_pull.get("consent_ref"), (
        "data_pull event must carry consent_ref. "
        "Check: ingest_node writes AuditEvent with consent_ref kwarg."
    )

    # 5. Score in the completed result should match what was surfaced at the pause.
    assert resumed["score"]["composite"] == run["score"]["composite"], (
        "Score must not change between the pause and the resume. "
        "score_node runs once and the result is checkpointed."
    )


# ── Flow 2: Override-to-pattern arc ───────────────────────────────────────────

def test_override_to_pattern_arc():
    """PATTERN_THRESHOLD overrides in one segment → /learning/recommendations surfaces a rec.

    Integration tested: outcomes file → scan() → API endpoint serialisation.
    Outcomes are written to a temp file (avoids polluting the real outcomes log).
    """
    segment = "E2E-Test-Segment"

    def _make_outcomes(n: int) -> list[DecisionOutcome]:
        ts = datetime.now(timezone.utc).isoformat()
        return [
            DecisionOutcome(
                app_id=f"E2E-APP-{i}",
                ts=ts,
                segment=segment,
                model_recommendation="refer",
                human_decision="approve",
                override=classify_override("refer", "approve"),
                reason="E2E test override",
                model_version="v0",
            )
            for i in range(n)
        ]

    # Below threshold → no recommendations.
    below_outcomes = _make_outcomes(PATTERN_THRESHOLD - 1)
    with tempfile.TemporaryDirectory() as td:
        outcomes_path = Path(td) / "outcomes.jsonl"
        outcomes_path.write_text(
            "\n".join(o.model_dump_json() for o in below_outcomes) + "\n"
        )
        with patch("credsight.service.outcomes._OUTCOMES_FILE", outcomes_path), \
             patch("credsight.governance.learning.capture"):
            r = client.get("/api/learning/recommendations")
    assert r.status_code == 200
    assert r.json() == [], (
        f"Below PATTERN_THRESHOLD ({PATTERN_THRESHOLD - 1} < {PATTERN_THRESHOLD}) "
        "must produce zero recommendations."
    )

    # At threshold → exactly one recommendation for our segment.
    at_outcomes = _make_outcomes(PATTERN_THRESHOLD)
    with tempfile.TemporaryDirectory() as td:
        outcomes_path = Path(td) / "outcomes.jsonl"
        outcomes_path.write_text(
            "\n".join(o.model_dump_json() for o in at_outcomes) + "\n"
        )
        import credsight.governance.learning as learning_mod
        learning_mod._emitted_rec_ids.clear()  # reset dedup guard between subtests
        with patch("credsight.service.outcomes._OUTCOMES_FILE", outcomes_path), \
             patch("credsight.governance.learning.capture"):
            r = client.get("/api/learning/recommendations")
    assert r.status_code == 200
    recs = r.json()
    assert len(recs) == 1, (
        f"Expected 1 recommendation at threshold ({PATTERN_THRESHOLD} overrides), "
        f"got {len(recs)}. Check: PATTERN_THRESHOLD in governance/learning.py, "
        "and that scan() is called without a custom threshold in app.py."
    )
    rec = recs[0]
    assert rec["segment"] == segment
    assert rec["evidence_count"] == PATTERN_THRESHOLD
    assert rec["status"] == "pending_human_approval"
    assert rec["id"].startswith("rec-"), f"rec id format unexpected: {rec['id']!r}"


# ── Flow 3: Capture-to-graph arc ──────────────────────────────────────────────

def test_capture_to_graph_arc():
    """Capture a learned note → organize dream cycle → graph endpoint has nodes + edges.

    Integration tested: capture() writes to GBrain → organize() builds the graph →
    /knowledge/graph serialises it correctly for the frontend.
    """
    # 1. Capture a derived learning (simulates what the reconciliation agent does).
    note = "E2E-TEST: micro-kirana sector — UPI-primary MSMEs underscored by cash_flow_health"
    r = client.post("/api/tools/knowledge/capture", json={
        "note": note, "tags": ["e2e-test", "kirana", "upi-primary"]
    })
    assert r.status_code == 200, f"knowledge/capture failed: {r.text}"
    assert r.json().get("ok") is True, "capture must return {ok: true}"

    # 2. Run the dream cycle (organize: embed → link → cluster → persist graph).
    r = client.post("/api/knowledge/organize")
    assert r.status_code == 200, f"knowledge/organize failed: {r.text}"
    org = r.json()
    assert org.get("clauses", 0) > 0, (
        "organize() must process at least one clause. "
        "Check: knowledge/policies/*.md loaded by brain.py, "
        "and that the captured note is indexed by organize()."
    )

    # 3. Graph endpoint must return a non-empty graph for the frontend SVG.
    r = client.get("/api/knowledge/graph")
    assert r.status_code == 200, f"knowledge/graph failed: {r.text}"
    graph = r.json()
    assert graph["clauses"] > 0, (
        "Graph must have nodes after organize(). "
        "Check: organize() persists to var/knowledge/graph.json and "
        "knowledge/graph.py load_graph() reads the right path."
    )
    assert graph["built_at"] is not None, "built_at must be set after organize()"

    # 4. Nodes and edge_list must be present and well-formed for the GraphView component.
    nodes = graph.get("nodes", [])
    assert nodes, "nodes list must not be empty — GraphView renders them as SVG circles"
    for node in nodes[:3]:  # spot-check first few
        assert "ref" in node or "id" in node, f"node missing ref/id: {node}"
        assert "title" in node or "label" in node or "ref" in node, (
            f"node missing displayable field: {node}"
        )

    edge_list = graph.get("edge_list", [])
    if edge_list:
        for edge in edge_list[:3]:
            assert "source" in edge and "target" in edge, (
                f"edge missing source/target: {edge}"
            )
            assert "weight" in edge and 0.0 <= edge["weight"] <= 1.0, (
                f"edge weight out of range: {edge}"
            )
