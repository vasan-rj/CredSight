"""Sandbox adapters — call IDBI's sandbox APIs. Stubbed with the real API shapes so
wiring them on shortlist is filling in the HTTP calls, not redesigning (ref-doc 05
§Sandbox-readiness checklist).

DO NOT call these until IDBI_SANDBOX_BASE_URL + key are set and the system is flipped to
`sandbox` mode in config. No real money movement during the challenge."""

from __future__ import annotations

from ..data.schema import ConsentArtefact, SourceKind


class _SandboxConnector:
    def __init__(self, system: SourceKind):
        self.system = system

    def fetch(self, msme_id: str, consent: ConsentArtefact, **kwargs) -> dict:
        # TODO(on shortlist): real consent-scoped HTTP call to the IDBI sandbox API for
        # self.system, mapped into the canonical shape. Honor retries + timeouts.
        raise NotImplementedError(
            f"Sandbox adapter for {self.system.value} not yet wired — flip to synthetic "
            f"mode or implement against IDBI sandbox APIs."
        )


_REGISTRY = {
    "aa": SourceKind.BANK_AA,
    "gst": SourceKind.GST,
    "upi": SourceKind.UPI,
    "epfo": SourceKind.EPFO,
    "bureau": SourceKind.BUREAU,
}


def get(system: str) -> _SandboxConnector:
    return _SandboxConnector(_REGISTRY[system])
