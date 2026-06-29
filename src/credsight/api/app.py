"""FastAPI app. Endpoints match frontend/src/api.ts:
  GET  /api/applications/{app_id}/hitl       -> HITLRequest
  GET  /api/applications/{app_id}/audit      -> AuditEvent[]
  GET  /api/portfolio                        -> MsmeSummary[]
  POST /api/applications/{app_id}/decision   -> { ok, status }

All data is computed by the real deterministic pipeline (credsight.service). No LLM in
the decision path. CORS is open for the Vite dev server."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
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
             "seed": d.seed, "sector": d.sector or SECTORS[d.archetype]} for d in DEMO]


@app.get("/api/gstin/{gstin}")
def gstin_lookup(gstin: str) -> dict:
    """Public GSTIN profile pre-fill — no auth. Fails gracefully (empty dict on error).
    NOT used as a scoring input; only pre-fills the upload wizard name + sector."""
    from ..data.gstin_lookup import lookup_gstin
    profile = lookup_gstin(gstin)
    if profile is None:
        return {}
    return {
        "legal_name": profile.legal_name,
        "trade_name": profile.trade_name,
        "state": profile.state,
        "status": profile.status,
        "registration_date": profile.registration_date,
        "business_type": profile.business_type,
    }


@app.post("/api/upload/parse")
async def upload_parse(
    app_id: str = Form(...),
    name: str = Form(...),
    sector: str = Form(...),
    gstin: str | None = Form(default=None),
    bank_csv: UploadFile | None = File(default=None),
    gst_data: UploadFile | None = File(default=None),
    upi_csv: UploadFile | None = File(default=None),
) -> dict:
    """Parse uploaded bank/GST/UPI files into a CanonicalProfile and persist it to
    var/canonical/{app_id}.json. Returns a preview of what was found — call
    POST /api/upload/run to score it."""
    from ..data.upload import build_canonical_from_upload, upload_preview

    bank_text = (await bank_csv.read()).decode("utf-8", errors="replace") if bank_csv else None
    gst_text  = (await gst_data.read()).decode("utf-8", errors="replace") if gst_data else None
    upi_text  = (await upi_csv.read()).decode("utf-8", errors="replace") if upi_csv else None

    try:
        cp = build_canonical_from_upload(
            app_id=app_id, name=name, sector=sector, gstin=gstin,
            bank_csv=bank_text, gst_data=gst_text, upi_csv=upi_text,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    out_path = Path("var") / "canonical" / f"{app_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(cp.model_dump_json(indent=2))
    return {"app_id": app_id, "preview": upload_preview(cp)}


@app.post("/api/upload/run")
def upload_run(body: dict) -> dict:
    """Score a pre-parsed upload. Expects { app_id, name? }.
    The canonical profile must have been created by POST /api/upload/parse first."""
    from ..agents.run import start_assessment_from_canonical

    app_id = body.get("app_id")
    if not app_id:
        raise HTTPException(422, "app_id required")
    name = body.get("name", "MSME")
    try:
        return start_assessment_from_canonical(app_id, name)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


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


# ── Learning Loop (D2) ───────────────────────────────────────────────────────

@app.get("/api/learning/summary")
def learning_summary() -> dict:
    """D2: recent decision activity — count, overrides up/down, unique segments."""
    from ..service.outcomes import query
    outcomes = query(days=30)
    return {
        "total_decisions": len(outcomes),
        "overrides_up": sum(1 for o in outcomes if o.override == "up"),
        "overrides_down": sum(1 for o in outcomes if o.override == "down"),
        "segment_count": len({o.segment for o in outcomes}),
        "window_days": 30,
    }


@app.get("/api/learning/recommendations")
def learning_recommendations() -> list[dict]:
    """D2: override patterns detected; each is a pending recalibration recommendation."""
    from ..governance.learning import scan
    return [r.model_dump() for r in scan()]


@app.post("/api/learning/recommendations/{rec_id}/approve")
def approve_recommendation(rec_id: str) -> dict:
    """D2: record human approval of a recalibration recommendation.
    Writes an immutable audit event and appends a model-version record."""
    import json
    from datetime import datetime, timezone

    from ..governance.audit import AuditEvent, AuditLog, EventType

    ts = datetime.now(timezone.utc).isoformat()
    AuditLog("system", base_dir=Path("audit")).append(
        AuditEvent("system", ts, EventType.HUMAN_DECISION, "risk_team",
                   {"action": "approve_recommendation", "rec_id": rec_id})
    )
    version_file = Path("var") / "model-versions.jsonl"
    version_recorded = False
    try:
        version_file.parent.mkdir(parents=True, exist_ok=True)
        with version_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "version": f"v-{ts[:10].replace('-', '')}",
                "changed": f"Recalibration approved: {rec_id}",
                "approved_by": "risk_team",
                "ts": ts,
                "rec_id": rec_id,
            }) + "\n")
        version_recorded = True
    except IOError:
        pass
    return {"ok": True, "rec_id": rec_id, "status": "approved", "version_recorded": version_recorded}


@app.get("/api/learning/model-versions")
def model_versions() -> list[dict]:
    """D2: ordered history of model recalibration approvals."""
    import json
    version_file = Path("var") / "model-versions.jsonl"
    if not version_file.exists():
        return []
    results = []
    for line in version_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            results.append(json.loads(line))
        except Exception:
            continue
    return results


# ── Knowledge graph (P3 stub — real cycle in knowledge/organize.py) ──────────

@app.post("/api/knowledge/organize")
def knowledge_organize() -> dict:
    """Run the GBrain dream cycle (nightly cron / demo button). Dedupes, links, clusters."""
    from ..knowledge.brain import organize
    return organize()


@app.get("/api/knowledge/graph")
def knowledge_graph() -> dict:
    """Return the persisted clause graph for frontend visualisation (nodes + edges +
    communities). Loads from var/knowledge/graph.json written by the last organize() cycle.
    Returns an empty-state dict when no graph has been built yet — caller should trigger
    POST /api/knowledge/organize first."""
    from ..knowledge.graph import load_graph
    raw = load_graph()
    if not raw:
        return {"clauses": 0, "edges": 0, "communities": 0, "community_detail": {},
                "dedup_candidates": 0, "dedup_pairs": [], "built_at": None,
                "nodes": [], "edge_list": []}
    return {
        "clauses":          raw.get("node_count", 0),
        "edges":            raw.get("edge_count", 0),
        "communities":      len(raw.get("communities", {})),
        "community_detail": raw.get("communities", {}),
        "dedup_candidates": len(raw.get("dedup_candidates", [])),
        "dedup_pairs":      raw.get("dedup_candidates", []),
        "built_at":         raw.get("built_at"),
        "nodes":            raw.get("nodes", []),
        "edge_list": [
            {"source": e["source"], "target": e["target"],
             "weight": e["weight"], "reason": e["reason"]}
            for e in raw.get("edges", [])
        ],
    }


def main() -> None:
    """Entrypoint for `credsight-api`."""
    import uvicorn

    # Mount sample files for the upload wizard download links.
    _samples = Path("samples")
    if _samples.exists():
        app.mount("/samples", StaticFiles(directory=str(_samples)), name="samples")

    uvicorn.run("credsight.api.app:app", host="0.0.0.0", port=8000, reload=False)
