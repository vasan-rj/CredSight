"""Governance invariants: HITL triggers and append-only audit log."""

from __future__ import annotations

from credsight.governance.audit import AuditEvent, AuditLog, EventType
from credsight.governance.hitl import requires_human
from credsight.scoring.model import predict
from credsight.scoring.policy import recommend
from credsight.scoring.schema import FeatureVector


def _fv(**kw):
    base = dict(app_id="APP1", features={}, n_sources=3, months_history=12,
                cross_source_agreement=1.0)
    base.update(kw)
    return FeatureVector(**base)


def test_low_confidence_forces_human():
    score = predict(_fv(n_sources=1, months_history=1, cross_source_agreement=0.4))
    rec = recommend(score)
    reasons = requires_human(score, rec)
    assert any("confidence" in r for r in reasons)


def test_reject_forces_human():
    # Empty features -> low composite -> not eligible -> must go to a human.
    score = predict(_fv())
    rec = recommend(score)
    if not rec.eligible:
        assert any("reject" in r for r in requires_human(score, rec))


def test_audit_log_appends(tmp_path):
    log = AuditLog("APP1", base_dir=tmp_path)
    log.append(AuditEvent("APP1", "2026-06-13T10:00:00Z", EventType.SCORE, "scoring",
                          {"composite": 718}, model_version="v0"))
    log.append(AuditEvent("APP1", "2026-06-13T10:00:01Z", EventType.HUMAN_DECISION,
                          "underwriter:u123", {"decision": "approve"}))
    rows = log.read_all()
    assert len(rows) == 2
    assert rows[0]["event_type"] == "score"
    assert rows[1]["actor"] == "underwriter:u123"
