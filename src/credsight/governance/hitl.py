"""HITL approval gate (FR-16/17/18). Decides when a case must interrupt to a human and
packages what the underwriter sees. The actual pause is a Deep Agents interrupt on the
money-moving tool (agents/orchestrator.py); this module holds the trigger logic + payload
so it's testable in isolation.

Trigger when ANY of: amount > threshold, recommendation == reject, confidence < floor,
out_of_policy. No downstream action runs until the human clears it."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import config
from ..scoring.policy import Recommendation
from ..scoring.schema import ScoreResult


@dataclass(frozen=True)
class HITLDecisionRequest:
    """What the underwriter console renders: recommendation + explanation + evidence."""

    app_id: str
    reasons: list[str]
    recommendation: Recommendation
    score: ScoreResult
    explanation: str  # plain-language, from the Explainability subagent


def requires_human(score: ScoreResult, rec: Recommendation) -> list[str]:
    """Return the list of trigger reasons. Empty list => may auto-flow (within risk appetite)."""
    reasons: list[str] = []
    if rec.amount > config.hitl.amount_threshold:
        reasons.append(
            f"amount {rec.amount:,.0f} > threshold {config.hitl.amount_threshold:,.0f}"
        )
    if not rec.eligible:
        reasons.append("recommendation is reject — every auto-reject needs human review")
    if score.confidence < config.hitl.confidence_floor:
        reasons.append(
            f"thin-file confidence {score.confidence} < floor {config.hitl.confidence_floor}"
        )
    if rec.out_of_policy:
        reasons.append("out-of-policy decision")
    return reasons
