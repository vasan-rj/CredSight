"""The orchestrator as a LangGraph StateGraph (ref-doc 02 §Orchestration & durability).

Nodes run the workflow: ingest -> reconcile -> score -> gate -> action. State (canonical
data, features, notes, audit refs) is offloaded to the virtual filesystem so context stays
lean. The credit decision is a REAL human-in-the-loop interrupt: at the gate the run pauses
(checkpointed), surfaces the recommendation + explanation + evidence, and resumes only when
a human supplies a decision via Command(resume=...).

The credit path is deterministic by design — the LLM never decides — so this graph runs
fully without any API key. The deepagents planning/subagent supervisor (agents/orchestrator)
is an optional layer on top (needs Python 3.11)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from ..data.schema import CanonicalProfile
from ..governance.audit import AuditEvent, AuditLog, EventType
from ..governance.hitl import requires_human
from ..scoring.policy import Recommendation
from ..scoring.schema import FeatureVector, ScoreResult
from . import tools

_VFS = Path("var")  # virtual filesystem root (gitignored working dirs live under here)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(rel: str, content: str) -> None:
    p = _VFS / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


class State(TypedDict, total=False):
    # All values are msgpack-native (dicts/lists/primitives) so checkpoints persist cleanly
    # across a real (e.g. Postgres) saver — objects are rebuilt inside nodes as needed.
    app_id: str
    name: str
    archetype: str
    seed: int
    consent_ref: str
    sector: str
    canonical: dict
    features: dict
    flags: list[dict]
    score: dict
    recommendation: dict
    explanation: str
    hitl_reasons: list[str]
    decision: dict | None
    status: str


def _audit(app_id: str) -> AuditLog:
    return AuditLog(app_id, base_dir=_VFS / "audit")


# --- Nodes ----------------------------------------------------------------

def ingest_node(state: State) -> dict:
    app_id = state["app_id"]
    cp = tools.tool_ingest(app_id, state["archetype"], state["seed"], state.get("name", "MSME"))
    _write(f"canonical/{app_id}.json", cp.model_dump_json(indent=2))
    _audit(app_id).append(AuditEvent(
        app_id, _now(), EventType.DATA_PULL, "consent_ingestion",
        {"consented_scope": [s.value for s in cp.consent.scope],
         "missing": [s.value for s in cp.missing_sources]},
        consent_ref=cp.consent.consent_id,
    ))
    return {"canonical": cp.model_dump(mode="json"), "consent_ref": cp.consent.consent_id,
            "sector": cp.profile.sector or "—"}


def reconcile_node(state: State) -> dict:
    app_id = state["app_id"]
    cp = CanonicalProfile(**state["canonical"])
    fv, flags = tools.tool_reconcile(cp)
    flag_dicts = [{"code": f.code, "severity": f.severity.value, "message": f.message,
                   "evidence": f.evidence} for f in flags]
    _write(f"features/{app_id}.json", fv.model_dump_json(indent=2))
    _write(f"recon/{app_id}.md", _recon_notes(fv, flag_dicts))
    log = _audit(app_id)
    for fd in flag_dicts:
        log.append(AuditEvent(app_id, _now(), EventType.RECON_FLAG, "reconciliation_enrichment", fd))
    return {"features": fv.model_dump(mode="json"), "flags": flag_dicts}


def score_node(state: State) -> dict:
    from ..knowledge.brain import search as kb_search

    app_id = state["app_id"]
    fv = FeatureVector(**state["features"])
    score = tools.tool_score(fv)
    rec = tools.tool_recommend(score)

    # Policy grounding: retrieve the clauses that apply to this case and cite them in the
    # recommendation + audit (the grounding rule — never decide ungrounded).
    clauses = kb_search(f"{rec.product} unsecured limit score band eligibility",
                        segment="micro enterprise thin file", k=3)
    rec_dict = {**asdict(rec), "policy_clause_refs": [c.ref for c in clauses]}

    log = _audit(app_id)
    log.append(AuditEvent(app_id, _now(), EventType.SCORE, "scoring_decisioning",
                          {"composite": score.composite, "confidence": score.confidence},
                          model_version=score.model_version))
    log.append(AuditEvent(app_id, _now(), EventType.RECOMMENDATION, "scoring_decisioning",
                          {"eligible": rec.eligible, "product": rec.product,
                           "amount": rec.amount,
                           "policy_clause_refs": rec_dict["policy_clause_refs"]}))
    return {"score": score.model_dump(mode="json"), "recommendation": rec_dict,
            "explanation": _explain(score)}


def gate_node(state: State) -> dict:
    """The human-in-the-loop gate. Pauses the run via interrupt() when review is required;
    resumes with the human's decision."""
    app_id = state["app_id"]
    score = ScoreResult(**state["score"])
    rec = Recommendation(**state["recommendation"])
    reasons = requires_human(score, rec)
    reasons += [f"fraud signal: {f['code']}" for f in state["flags"] if f["severity"] == "fraud"]

    if not reasons:
        status = "approved" if rec.eligible else "rejected"
        return {"hitl_reasons": [], "status": status, "decision": None}

    # Idempotent: on resume LangGraph re-executes this node up to interrupt(), so guard
    # against double-logging the same HITL request.
    log = _audit(app_id)
    if not any(e["event_type"] == EventType.HITL_REQUEST.value for e in log.read_all()):
        log.append(AuditEvent(app_id, _now(), EventType.HITL_REQUEST, "orchestrator",
                              {"reasons": reasons}))
    # PAUSE. The run is checkpointed; resume with Command(resume={"decision":..,"reason":..}).
    decision = interrupt({
        "app_id": app_id,
        "reasons": reasons,
        "recommendation": state["recommendation"],
        "score": state["score"],
        "explanation": state["explanation"],
    })

    underwriter = decision.get("underwriter", "underwriter:demo")
    _audit(app_id).append(AuditEvent(app_id, _now(), EventType.HUMAN_DECISION, underwriter,
                                     {"decision": decision.get("decision"),
                                      "reason": decision.get("reason", "")}))
    status = {"approve": "approved", "override": "rejected",
              "request_info": "needs_info"}.get(decision.get("decision"), "pending_human")
    return {"hitl_reasons": reasons, "status": status, "decision": decision}


def action_node(state: State) -> dict:
    """Post-approval only: execute the offer (the only node with action permissions)."""
    app_id = state["app_id"]
    if state.get("status") != "approved":
        return {}
    rec = Recommendation(**state["recommendation"])
    offer = tools.tool_action_create_offer(app_id, rec)
    _audit(app_id).append(AuditEvent(app_id, _now(), EventType.ACTION, "offer_action",
                                     {"action": "create_offer", **offer}))
    return {}


# --- helpers --------------------------------------------------------------

def _explain(score) -> str:
    from .narrate import generate_explanation

    return generate_explanation(score)


def _recon_notes(fv, flag_dicts: list[dict]) -> str:
    lines = [f"# Reconciliation notes — {fv.app_id}", "",
             f"- sources present: {fv.n_sources}", f"- months history: {fv.months_history}",
             f"- cross-source agreement: {fv.cross_source_agreement}", "", "## Flags"]
    lines += [f"- [{f['severity']}] {f['code']}: {f['message']}" for f in flag_dicts] or ["- none"]
    return "\n".join(lines)


# --- build ----------------------------------------------------------------

def build_graph(checkpointer=None):
    """Compile the orchestrator graph. A checkpointer is REQUIRED for the HITL interrupt
    to pause/resume; defaults to an in-memory saver (swap for a persistent one in prod)."""
    g = StateGraph(State)
    g.add_node("ingest", ingest_node)
    g.add_node("reconcile", reconcile_node)
    g.add_node("score", score_node)
    g.add_node("gate", gate_node)
    g.add_node("action", action_node)
    g.add_edge(START, "ingest")
    g.add_edge("ingest", "reconcile")
    g.add_edge("reconcile", "score")
    g.add_edge("score", "gate")
    g.add_edge("gate", "action")
    g.add_edge("action", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())
