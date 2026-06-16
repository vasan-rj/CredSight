"""Drive the orchestrator graph: start an assessment (runs to the HITL pause or to a
terminal auto-decision) and resume it with a human decision. One LangGraph thread per
application, so a paused run survives and resumes exactly where it stopped.

This is what the API + the demo call. The graph + checkpointer give durable, resumable
runs for free (ref-doc 02/07)."""

from __future__ import annotations

from typing import Any

from langgraph.types import Command

from .graph import build_graph

# One compiled graph with an in-memory checkpointer for the process lifetime.
_GRAPH = build_graph()


def _cfg(app_id: str) -> dict:
    return {"configurable": {"thread_id": app_id}}


def _result(app_id: str, out: dict) -> dict:
    """Normalise a graph output into one rich shape the UI consumes whether the run paused
    at the HITL gate or auto-decided — always carries the full score + recommendation +
    explanation so the Health Card renders either way."""
    interrupts = out.get("__interrupt__")
    if interrupts:
        p = interrupts[0].value
        return {
            "app_id": app_id, "status": "pending_human", "paused": True,
            "reasons": p["reasons"], "score": p["score"],
            "recommendation": p["recommendation"], "explanation": p["explanation"],
            "decision": None,
        }
    return {
        "app_id": app_id, "status": out.get("status"), "paused": False,
        "reasons": out.get("hitl_reasons", []), "score": out["score"],
        "recommendation": out["recommendation"], "explanation": out.get("explanation", ""),
        "decision": out.get("decision"),
    }


def start_assessment(app_id: str, archetype: str, seed: int, name: str = "MSME") -> dict:
    """Run a fresh assessment. Returns either the HITL interrupt payload (paused) or the
    terminal auto-decision."""
    state = {"app_id": app_id, "archetype": archetype, "seed": seed, "name": name}
    out: dict[str, Any] = _GRAPH.invoke(state, _cfg(app_id))
    return _result(app_id, out)


def resume_assessment(app_id: str, decision: str, reason: str = "",
                      underwriter: str = "underwriter:demo") -> dict:
    """Resume a paused run with the underwriter's decision; runs to completion."""
    payload = {"decision": decision, "reason": reason, "underwriter": underwriter}
    out: dict[str, Any] = _GRAPH.invoke(Command(resume=payload), _cfg(app_id))
    return _result(app_id, out)
