"""Synthetic adapters — serve generated archetype data from data/synthetic during the
challenge. Same interface as the sandbox adapters; the swap is a config flip.

Reads the per-MSME bundle written by data.generators and slices out the requested
source. Consent scope is enforced before any read."""

from __future__ import annotations

import json

from ..config import config
from ..data.schema import ConsentArtefact, SourceKind
from .base import _check_consent


class _SyntheticConnector:
    def __init__(self, system: SourceKind):
        self.system = system

    def fetch(self, msme_id: str, consent: ConsentArtefact, **kwargs) -> dict:
        _check_consent(self.system, consent)
        bundle_path = config.data_dir / f"{msme_id}.json"
        if not bundle_path.exists():
            raise FileNotFoundError(
                f"No synthetic bundle for {msme_id} at {bundle_path}. "
                f"Run `credsight-gen-data` first."
            )
        bundle = json.loads(bundle_path.read_text())
        return bundle.get(self.system.value, {})


_REGISTRY = {
    "aa": SourceKind.BANK_AA,
    "gst": SourceKind.GST,
    "upi": SourceKind.UPI,
    "epfo": SourceKind.EPFO,
    "bureau": SourceKind.BUREAU,
}


def get(system: str) -> _SyntheticConnector:
    return _SyntheticConnector(_REGISTRY[system])
