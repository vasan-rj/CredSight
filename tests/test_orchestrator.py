"""Orchestrator graph: durable run, real HITL interrupt, resume. Uses a fresh compiled
graph per test (own in-memory checkpointer) so threads don't bleed across tests."""

from __future__ import annotations

import pytest

pytest.importorskip("langgraph")

from langgraph.types import Command  # noqa: E402

from credsight.agents.graph import build_graph  # noqa: E402


def _run(app_id: str, archetype: str, seed: int):
    graph = build_graph()
    cfg = {"configurable": {"thread_id": app_id}}
    out = graph.invoke({"app_id": app_id, "archetype": archetype, "seed": seed,
                        "name": "T"}, cfg)
    return graph, cfg, out


def test_strong_auto_approves_under_threshold():
    """Strong archetype (offer ~500k) should auto-approve since 500k < 600k HITL threshold.
    Previously tested HITL pause at the old 200k threshold — now the demo beat is
    'strong applicant flows through without friction'."""
    _, _, out = _run("T-STRONG", "strong", 102)
    assert "__interrupt__" not in out, (
        "Strong archetype (offer ~500k) should auto-approve under the 600k HITL threshold."
    )
    assert out.get("status") == "approved"


def test_fraud_forces_hitl_with_fraud_reasons():
    _, _, out = _run("T-FRAUD", "fraud", 104)
    assert "__interrupt__" in out
    reasons = out["__interrupt__"][0].value["reasons"]
    assert any("fraud signal" in r for r in reasons)


def test_resume_approve_reaches_action():
    # Stressed archetype (rejection) always hits the HITL gate.
    graph, cfg, out = _run("T-RESUME", "stressed", 103)
    assert "__interrupt__" in out  # paused
    final = graph.invoke(Command(resume={"decision": "approve", "reason": "ok"}), cfg)
    assert final["status"] == "approved"
    # Audit trail captured the human decision + the post-approval action.
    from pathlib import Path

    from credsight.governance.audit import AuditLog
    types = [e["event_type"] for e in AuditLog(final.get("app_id", "T-RESUME"), base_dir=Path("var") / "audit").read_all()]
    assert "human_decision" in types
    assert "action" in types


def test_reject_routes_to_human():
    _, _, out = _run("T-STRESSED", "stressed", 103)
    # Stressed -> reject -> human review (every auto-reject needs sign-off).
    assert "__interrupt__" in out
    assert any("reject" in r for r in out["__interrupt__"][0].value["reasons"])
