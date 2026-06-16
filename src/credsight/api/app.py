"""FastAPI app. Endpoints match frontend/src/api.ts:
  GET  /api/applications/{app_id}/hitl       -> HITLRequest
  GET  /api/applications/{app_id}/audit      -> AuditEvent[]
  GET  /api/portfolio                        -> MsmeSummary[]
  POST /api/applications/{app_id}/decision   -> { ok, status }

All data is computed by the real deterministic pipeline (credsight.service). No LLM in
the decision path. CORS is open for the Vite dev server."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ..governance.audit import AuditLog
from ..service.pipeline import record_decision
from ..service.store import store
from ..scoring.model import predict
from ..scoring.schema import FeatureVector, ScoreResult
from .schemas import (
    DecisionIn,
    DecisionOut,
    KnowledgeCaptureIn,
    KnowledgeSearchIn,
    ResumeIn,
    RunIn,
    hitl_to_wire,
    portfolio_row,
)

app = FastAPI(title="CredSight API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/portfolio")
def get_portfolio() -> list[dict]:
    return [portfolio_row(a) for a in store.all()]


@app.get("/api/applications/{app_id}/hitl")
def get_hitl(app_id: str) -> dict:
    app_rec = store.get(app_id)
    if app_rec is None:
        raise HTTPException(404, f"unknown application {app_id}")
    return hitl_to_wire(app_rec)


@app.get("/api/applications/{app_id}/audit")
def get_audit(app_id: str) -> list[dict]:
    if store.get(app_id) is None:
        raise HTTPException(404, f"unknown application {app_id}")
    return AuditLog(app_id, base_dir=Path("audit")).read_all()


@app.post("/api/applications/{app_id}/decision")
def post_decision(app_id: str, body: DecisionIn) -> DecisionOut:
    app_rec = store.get(app_id)
    if app_rec is None:
        raise HTTPException(404, f"unknown application {app_id}")
    updated = record_decision(app_rec, body.decision, body.reason)
    store.put(updated)
    return DecisionOut(ok=True, status=updated.status.value)


# --- Orchestrator (LangGraph) endpoints: drive a live run through the HITL interrupt ---

@app.get("/api/catalog")
def catalog() -> list[dict]:
    """The demo applicants the UI can run through the orchestrator (archetype + seed)."""
    from ..data.generators.generate import SECTORS
    from ..service.demo_seed import DEMO

    return [{"app_id": d.app_id, "name": d.name, "archetype": d.archetype.value,
             "seed": d.seed, "sector": SECTORS[d.archetype]} for d in DEMO]


@app.post("/api/orchestrator/run")
def orchestrator_run(body: RunIn) -> dict:
    """Start an assessment through the orchestrator graph. Returns the full result (score +
    recommendation + explanation) plus whether it paused at the HITL gate."""
    from ..agents.run import start_assessment

    return start_assessment(body.app_id, body.archetype, body.seed, body.name)


@app.post("/api/orchestrator/resume")
def orchestrator_resume(body: ResumeIn) -> dict:
    """Resume a paused run with the underwriter's decision; runs to completion."""
    from ..agents.run import resume_assessment

    return resume_assessment(body.app_id, body.decision, body.reason, body.underwriter)


@app.get("/api/orchestrator/{app_id}/audit")
def orchestrator_audit(app_id: str) -> list[dict]:
    """Append-only audit trail written by the orchestrator run (the virtual filesystem)."""
    return AuditLog(app_id, base_dir=Path("var") / "audit").read_all()


# --- Normal REST API tools: in-process deterministic services (also back the UI) ---

@app.post("/api/tools/score")
def tool_score(fv: FeatureVector) -> ScoreResult:
    """score_model.predict over REST — the deterministic, versioned scoring core.
    Same contract as the would-be MCP decisioning tool; kept in-process (no LLM, no network)."""
    return predict(fv)


@app.post("/api/tools/knowledge/search")
def tool_knowledge_search(body: KnowledgeSearchIn) -> dict:
    """knowledge.search — retrieve policy clauses for the applicant's segment (GBrain-backed)."""
    from ..knowledge.brain import search

    clauses = search(body.query, body.segment)
    return {
        "clauses": [{"ref": c.ref, "text": c.text, "page": c.page} for c in clauses],
        "sources": sorted({c.source for c in clauses}),
    }


@app.post("/api/tools/knowledge/capture")
def tool_knowledge_capture(body: KnowledgeCaptureIn) -> dict:
    """knowledge.capture — write a derived learning (e.g. a new fraud pattern) into GBrain."""
    from ..knowledge.brain import capture

    return {"ok": capture(body.note, body.tags)}


def main() -> None:
    """Entrypoint for `credsight-api`."""
    import uvicorn

    uvicorn.run("credsight.api.app:app", host="0.0.0.0", port=8000, reload=False)
