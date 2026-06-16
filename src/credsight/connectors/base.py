"""Connector interface + factory. One protocol per data system; the factory returns the
synthetic or sandbox implementation based on config — agents stay adapter-agnostic.

All ingestion connectors are read-only and consent-scoped: a connector must refuse to
return data outside the consent artefact's scope (enforced here + at the MCP boundary)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..config import config
from ..data.schema import ConsentArtefact, SourceKind


@runtime_checkable
class DataConnector(Protocol):
    """A read-only, consent-scoped source connector."""

    system: SourceKind

    def fetch(self, msme_id: str, consent: ConsentArtefact, **kwargs) -> dict:
        """Return raw source data. Must raise if `self.system` is not in consent.scope."""
        ...


def _check_consent(system: SourceKind, consent: ConsentArtefact) -> None:
    if system not in consent.scope:
        raise PermissionError(
            f"Consent {consent.consent_id} does not cover {system.value}; refusing fetch."
        )


def get_connector(system: str) -> DataConnector:
    """Return the active connector for a system, honoring config.adapter_mode(system).

    TODO(days 7-10): register sandbox adapters. Synthetic adapters are wired in
    connectors.synthetic; sandbox stubs in connectors.sandbox."""
    mode = config.adapter_mode(system)
    if mode == "synthetic":
        from . import synthetic

        return synthetic.get(system)
    if mode == "sandbox":
        from . import sandbox

        return sandbox.get(system)
    raise ValueError(f"Unknown adapter mode {mode!r} for system {system!r}")


__all__ = ["DataConnector", "get_connector", "_check_consent"]
