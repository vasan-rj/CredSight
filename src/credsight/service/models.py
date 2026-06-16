"""Application records held by the service. These are the runtime state objects; the API
layer maps them to response schemas (which mirror the frontend types)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..scoring.policy import Recommendation
from ..scoring.schema import ScoreResult


class Status(str, Enum):
    PENDING_HUMAN = "pending_human"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_INFO = "needs_info"


@dataclass
class Application:
    app_id: str
    name: str
    sector: str
    score: ScoreResult
    recommendation: Recommendation
    hitl_reasons: list[str]
    explanation: str
    status: Status
    consent_ref: str
    decision_reason: str | None = None
    decided_by: str | None = None
    # Feature inputs kept for re-score / audit reproducibility.
    feature_seed: dict = field(default_factory=dict)
