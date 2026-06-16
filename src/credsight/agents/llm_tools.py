"""LangChain tools for the deepagents supervisor — the id-based, JSON-in/JSON-out surface
an LLM can actually sequence (the orchestrator graph in graph.py uses the typed objects
directly; this is the LLM-drivable mirror of the same services).

Working state is keyed by app_id in a process-local store so tools compose across a run
without passing big objects through the model. Every tool wraps a real deterministic
service — the LLM orchestrates, it never computes the score. The money-moving tool
(`create_offer`) is the one the supervisor is told to gate behind human approval."""

from __future__ import annotations

import json
from dataclasses import asdict

from langchain_core.tools import tool

from ..knowledge.brain import search as kb_search
from . import tools as svc

# Process-local working state per application (the agent's "scratchpad").
_STATE: dict[str, dict] = {}


@tool
def ingest(app_id: str, archetype: str, seed: int) -> str:
    """Pull and normalise an MSME's alternate data with consent (synthetic). archetype is
    one of thin_file|strong|stressed|fraud. Returns a short summary."""
    cp = svc.tool_ingest(app_id, archetype, seed)
    _STATE.setdefault(app_id, {})["cp"] = cp
    return f"Ingested {cp.profile.name}: {len(cp.accounts)} accounts, " \
           f"{len(cp.gst_returns)} GST returns, {len(cp.upi_txns)} UPI txns; " \
           f"missing={[s.value for s in cp.missing_sources]}; consent={cp.consent.consent_id}"


@tool
def reconcile(app_id: str) -> str:
    """Cross-validate sources, flag fraud, derive features. Call after ingest. Returns the
    rule-backed flags (JSON)."""
    cp = _STATE.get(app_id, {}).get("cp")
    if cp is None:
        return "error: ingest first"
    fv, flags = svc.tool_reconcile(cp)
    _STATE[app_id]["fv"] = fv
    return json.dumps({"n_features": len(fv.features), "confidence_inputs": {
        "n_sources": fv.n_sources, "months": fv.months_history,
        "agreement": fv.cross_source_agreement},
        "flags": [{"code": f.code, "severity": f.severity.value} for f in flags]})


@tool
def score(app_id: str) -> str:
    """Compute the deterministic health score + policy-checked recommendation. Call after
    reconcile. The LLM must NOT invent the score — this calls the versioned model. Returns
    score + recommendation (JSON)."""
    fv = _STATE.get(app_id, {}).get("fv")
    if fv is None:
        return "error: reconcile first"
    s = svc.tool_score(fv)
    rec = svc.tool_recommend(s)
    _STATE[app_id].update(score=s, rec=rec)
    return json.dumps({"composite": s.composite, "confidence": s.confidence,
                       "recommendation": asdict(rec)})


@tool
def knowledge_search(query: str, segment: str = "") -> str:
    """Retrieve applicable credit-policy clauses to ground the decision. Returns cited
    clauses (JSON) — reference their refs in any rationale."""
    clauses = kb_search(query, segment or None)
    return json.dumps([{"ref": c.ref, "title": c.title} for c in clauses])


@tool
def create_offer(app_id: str, amount: float, rate: float, tenor: int) -> str:
    """Execute the loan offer in the bank's systems. MONEY-MOVING ACTION — only after a
    human has approved at the HITL gate. Idempotent per app_id."""
    rec = _STATE.get(app_id, {}).get("rec")
    offer = svc.tool_action_create_offer(app_id, rec) if rec else {
        "offer_id": f"OFFER-{app_id}", "amount": amount, "rate": rate, "tenor_months": tenor}
    return json.dumps(offer)


# Tool groupings for the supervisor + subagents.
INGEST_TOOLS = [ingest]
RECON_TOOLS = [reconcile, knowledge_search]
SCORE_TOOLS = [score, knowledge_search]
ACTION_TOOLS = [create_offer]
ALL_TOOLS = [ingest, reconcile, score, knowledge_search, create_offer]
