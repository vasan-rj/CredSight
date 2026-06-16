"""Immutable audit log (FR-24) — the demo's trust centrepiece. Append-only record of
every state transition, data pull (with consent-artefact ref), model version + I/O, tool
action, and human decision.

During the challenge this writes to audit/{app_id}.log in the virtual filesystem (visible
on stage) and mirrors to the store. In production point AuditLog at an append-only
Postgres table / WORM store — same interface."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path


class EventType(str, Enum):
    CONSENT = "consent"
    DATA_PULL = "data_pull"
    RECON_FLAG = "recon_flag"
    SCORE = "score"
    RECOMMENDATION = "recommendation"
    HITL_REQUEST = "hitl_request"
    HUMAN_DECISION = "human_decision"
    ACTION = "action"
    ERROR = "error"


@dataclass(frozen=True)
class AuditEvent:
    app_id: str
    ts: str  # ISO8601 — passed in by the caller (deterministic, testable)
    event_type: EventType
    actor: str  # subagent name or human identity
    detail: dict
    # Provenance refs that make a decision defensible.
    consent_ref: str | None = None
    model_version: str | None = None


class AuditLog:
    """Append-only. No update/delete methods by design."""

    def __init__(self, app_id: str, base_dir: Path = Path("audit")):
        self.app_id = app_id
        base_dir.mkdir(parents=True, exist_ok=True)
        self._path = base_dir / f"{app_id}.log"

    def append(self, event: AuditEvent) -> None:
        line = json.dumps({**asdict(event), "event_type": event.event_type.value})
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def read_all(self) -> list[dict]:
        if not self._path.exists():
            return []
        return [json.loads(ln) for ln in self._path.read_text().splitlines() if ln.strip()]
