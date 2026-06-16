"""Shared helpers for the MCP tool servers.

Ingestion tools are read-only and consent-scoped: every fetch goes through the connector
layer (synthetic <-> sandbox via config), and the connector refuses any source outside the
consent artefact's scope (enforced at this boundary — FR-3)."""

from __future__ import annotations

from datetime import date

from ..connectors import get_connector
from ..data.schema import ConsentArtefact, SourceKind

# Fixed validity window for synthetic consent artefacts (deterministic).
_GRANTED = date(2026, 1, 1)
_VALID_UNTIL = date(2026, 12, 31)


def make_consent(consent_id: str, scope: list[str]) -> ConsentArtefact:
    return ConsentArtefact(
        consent_id=consent_id,
        scope=[SourceKind(s) for s in scope],
        granted_on=_GRANTED,
        valid_until=_VALID_UNTIL,
    )


def fetch_source(system: str, msme_id: str, consent_id: str, scope: list[str]) -> dict:
    """Consent-scoped read of one source via its connector. Raises PermissionError if the
    system is not within the consent scope."""
    consent = make_consent(consent_id, scope)
    connector = get_connector(system)  # honors config.adapter_mode(system): synthetic|sandbox
    return connector.fetch(msme_id, consent)
