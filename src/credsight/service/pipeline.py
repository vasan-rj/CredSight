"""The assessment pipeline: feature vector -> deterministic score -> policy recommendation
-> HITL trigger check -> faithful explanation -> audit events.

This is the real core path (no LLM, no mocks): scoring.predict, policy.recommend,
hitl.requires_human, governance.audit all run for real. The explanation is built by
faithfulness.safe_template (faithful by construction) until the LLM Explainability
subagent is wired (days 11-14)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..governance.audit import AuditEvent, AuditLog, EventType
from ..governance.hitl import requires_human
from ..reconciliation.rules import Flag, Severity
from ..scoring.model import predict
from ..scoring.policy import recommend
from ..scoring.schema import FeatureVector
from .models import Application, Status

_AUDIT_DIR = Path("audit")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _explanation(score, confidence_note: bool) -> str:
    # Faithfulness-gated LLM narration when available, else the deterministic template.
    from ..agents.narrate import generate_explanation

    return generate_explanation(score)


def assess(fv: FeatureVector, *, name: str, sector: str, consent_ref: str,
           flags: list[Flag] | None = None) -> Application:
    """Run the full deterministic assessment for one applicant and emit audit events."""
    flags = flags or []
    log = AuditLog(fv.app_id, base_dir=_AUDIT_DIR)

    log.append(AuditEvent(fv.app_id, _now(), EventType.DATA_PULL, "consent_ingestion",
                          {"n_sources": fv.n_sources, "months_history": fv.months_history},
                          consent_ref=consent_ref))

    for f in flags:
        log.append(AuditEvent(fv.app_id, _now(), EventType.RECON_FLAG,
                              "reconciliation_enrichment",
                              {"code": f.code, "severity": f.severity.value,
                               "message": f.message, "evidence": f.evidence}))

    score = predict(fv)
    log.append(AuditEvent(fv.app_id, _now(), EventType.SCORE, "scoring_decisioning",
                          {"composite": score.composite, "confidence": score.confidence},
                          model_version=score.model_version))

    rec = recommend(score)
    log.append(AuditEvent(fv.app_id, _now(), EventType.RECOMMENDATION, "scoring_decisioning",
                          {"eligible": rec.eligible, "product": rec.product,
                           "amount": rec.amount}))

    reasons = requires_human(score, rec)
    # Any fraud-severity reconciliation flag forces human review (FR-6/16).
    fraud_flags = [f for f in flags if f.severity == Severity.FRAUD]
    if fraud_flags:
        reasons = reasons + [f"fraud signal: {f.code}" for f in fraud_flags]
    explanation = _explanation(score, confidence_note=True)

    if reasons:
        status = Status.PENDING_HUMAN
        log.append(AuditEvent(fv.app_id, _now(), EventType.HITL_REQUEST, "orchestrator",
                              {"reasons": reasons}))
    else:
        status = Status.APPROVED if rec.eligible else Status.REJECTED

    return Application(
        app_id=fv.app_id, name=name, sector=sector, score=score, recommendation=rec,
        hitl_reasons=reasons, explanation=explanation, status=status,
        consent_ref=consent_ref, feature_seed=dict(fv.features),
    )


def record_decision(app: Application, decision: str, reason: str,
                    underwriter: str = "underwriter:demo") -> Application:
    """Apply an underwriter decision, log it immutably, and resume (status transition)."""
    log = AuditLog(app.app_id, base_dir=_AUDIT_DIR)
    log.append(AuditEvent(app.app_id, _now(), EventType.HUMAN_DECISION, underwriter,
                          {"decision": decision, "reason": reason}))
    mapping = {"approve": Status.APPROVED, "override": Status.REJECTED,
               "request_info": Status.NEEDS_INFO}
    app.status = mapping.get(decision, app.status)
    app.decision_reason = reason
    app.decided_by = underwriter
    if app.status == Status.APPROVED:
        # Post-approval the Action subagent would execute the offer (FR-19). Logged here.
        log.append(AuditEvent(app.app_id, _now(), EventType.ACTION, "offer_action",
                              {"action": "create_offer", "amount": app.recommendation.amount,
                               "idempotency_key": app.app_id}))
    return app
