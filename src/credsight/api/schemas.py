"""Response/request schemas. Mirror frontend/src/types.ts exactly so the UI can flip
USE_MOCK=false and consume these unchanged. Adapters convert service dataclasses ->
these wire models."""

from __future__ import annotations

from dataclasses import asdict

from pydantic import BaseModel

from ..service.models import Application
from ..scoring.schema import ScoreResult


class DecisionIn(BaseModel):
    decision: str  # "approve" | "override" | "request_info"
    reason: str = ""


class DecisionOut(BaseModel):
    ok: bool
    status: str


class RunIn(BaseModel):
    app_id: str
    archetype: str = "thin_file"  # thin_file | strong | stressed | fraud
    seed: int = 101
    name: str = "MSME"


class ResumeIn(BaseModel):
    app_id: str
    decision: str  # approve | override | request_info
    reason: str = ""
    underwriter: str = "underwriter:demo"


class KnowledgeSearchIn(BaseModel):
    query: str
    segment: str | None = None


class KnowledgeCaptureIn(BaseModel):
    note: str
    tags: list[str] = []


def score_to_wire(score: ScoreResult) -> dict:
    # Pydantic v2 serializes enum-keyed dicts to their values ("cash_flow_health", ...).
    return score.model_dump(mode="json")


def hitl_to_wire(app: Application) -> dict:
    return {
        "app_id": app.app_id,
        "reasons": app.hitl_reasons,
        "explanation": app.explanation,
        "score": score_to_wire(app.score),
        "recommendation": asdict(app.recommendation),
    }


def portfolio_row(app: Application) -> dict:
    return {
        "app_id": app.app_id,
        "name": app.name,
        "sector": app.sector,
        "composite": app.score.composite,
        "confidence": app.score.confidence,
        "status": app.status.value,
    }
