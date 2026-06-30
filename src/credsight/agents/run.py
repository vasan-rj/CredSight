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
            "pathway": p.get("pathway"), "decision": None,
            "needs": out.get("needs"), "product_matches": out.get("product_matches"),
        }
    return {
        "app_id": app_id, "status": out.get("status"), "paused": False,
        "reasons": out.get("hitl_reasons", []), "score": out["score"],
        "recommendation": out["recommendation"], "explanation": out.get("explanation", ""),
        "pathway": out.get("pathway"), "decision": out.get("decision"),
        "needs": out.get("needs"), "product_matches": out.get("product_matches"),
    }


def start_assessment(app_id: str, archetype: str, seed: int, name: str = "MSME") -> dict:
    """Run a fresh assessment. Returns either the HITL interrupt payload (paused) or the
    terminal auto-decision."""
    state = {"app_id": app_id, "archetype": archetype, "seed": seed, "name": name}
    out: dict[str, Any] = _GRAPH.invoke(state, _cfg(app_id))
    return _result(app_id, out)


def start_assessment_from_canonical(app_id: str, name: str = "MSME") -> dict:
    """Start an assessment from a pre-built CanonicalProfile (upload path).

    The canonical profile must exist at var/canonical/{app_id}.json — written by
    POST /api/upload/parse before this is called. Ingest node detects the pre-loaded
    canonical and skips re-ingestion; all downstream nodes run unchanged.
    """
    import json
    from pathlib import Path

    cp_path = Path("var") / "canonical" / f"{app_id}.json"
    if not cp_path.exists():
        raise FileNotFoundError(
            f"No canonical profile at {cp_path}. Call POST /api/upload/parse first."
        )
    canonical = json.loads(cp_path.read_text())
    state: dict[str, Any] = {
        "app_id": app_id, "name": name, "canonical": canonical,
        "archetype": "upload", "seed": 0,
    }
    out: dict[str, Any] = _GRAPH.invoke(state, _cfg(app_id))
    return _result(app_id, out)


def resume_assessment(app_id: str, decision: str, reason: str = "",
                      underwriter: str = "underwriter:demo") -> dict:
    """Resume a paused run with the underwriter's decision; runs to completion."""
    payload = {"decision": decision, "reason": reason, "underwriter": underwriter}
    out: dict[str, Any] = _GRAPH.invoke(Command(resume=payload), _cfg(app_id))
    return _result(app_id, out)
