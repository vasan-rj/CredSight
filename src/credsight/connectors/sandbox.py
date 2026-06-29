"""Sandbox adapters — call IDBI's sandbox APIs. AA and GST are wired with real HTTP
calls (10s timeout, 2 retries, exponential backoff). UPI/EPFO/Bureau raise
NotImplementedError until the endpoint contract is confirmed post-hackathon.

To activate: set CREDSIGHT_ADAPTER_AA=sandbox and CREDSIGHT_ADAPTER_GST=sandbox in .env,
plus IDBI_SANDBOX_BASE_URL and IDBI_SANDBOX_API_KEY. No real money movement during
the challenge — no action endpoints are in scope here."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..config import config
from ..data.schema import ConsentArtefact, SourceKind


def _base_url() -> str:
    url = getattr(config, "idbi_sandbox_base_url", None) or ""
    if not url:
        raise EnvironmentError(
            "IDBI_SANDBOX_BASE_URL not set. Add it to .env and set "
            "CREDSIGHT_ADAPTER_AA=sandbox / CREDSIGHT_ADAPTER_GST=sandbox."
        )
    return url.rstrip("/")


def _api_key() -> str:
    key = getattr(config, "idbi_sandbox_api_key", None) or ""
    if not key:
        raise EnvironmentError(
            "IDBI_SANDBOX_API_KEY not set. Add it to .env alongside IDBI_SANDBOX_BASE_URL."
        )
    return key


def _request(method: str, url: str, body: dict | None = None, timeout: int = 10) -> Any:
    """Perform an HTTP call with 2 retries and exponential backoff (1s, 2s)."""
    data = json.dumps(body).encode() if body else None
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None  # resource not found → empty / missing, not an error
            last_exc = exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_exc = exc
        if attempt < 2:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Sandbox request failed after 3 attempts: {last_exc}") from last_exc


class _AAConnector:
    system = SourceKind.BANK_AA

    def fetch(self, msme_id: str, consent: ConsentArtefact, **kwargs) -> dict:
        if SourceKind.BANK_AA not in consent.scope:
            raise PermissionError(f"Consent {consent.consent_id} does not cover bank_aa.")

        base = _base_url()
        # 1. Create / retrieve a consent artefact in the sandbox.
        consent_payload = {
            "consent_id": consent.consent_id,
            "msme_id": msme_id,
            "scope": [s.value for s in consent.scope],
            "valid_until": consent.valid_until.isoformat(),
        }
        consent_resp = _request("POST", f"{base}/aa/consent", body=consent_payload) or {}
        sandbox_consent_id = consent_resp.get("consent_id", consent.consent_id)

        # 2. Fetch consented data.
        data_resp = _request("GET", f"{base}/aa/data/{sandbox_consent_id}") or {}
        accounts = data_resp.get("accounts", [])
        txns     = data_resp.get("txns", [])

        if not accounts and not txns:
            return {"accounts": [], "txns": [], "_missing": True}
        return {"accounts": accounts, "txns": txns}


class _GSTConnector:
    system = SourceKind.GST

    def fetch(self, msme_id: str, consent: ConsentArtefact, **kwargs) -> dict:
        if SourceKind.GST not in consent.scope:
            raise PermissionError(f"Consent {consent.consent_id} does not cover gst.")

        base = _base_url()
        gstin = kwargs.get("gstin") or msme_id
        from_period = kwargs.get("from_period", "")
        to_period   = kwargs.get("to_period", "")
        params = urllib.parse.urlencode({k: v for k, v in
                                         {"from": from_period, "to": to_period}.items() if v})
        url = f"{base}/gst/returns/{gstin}"
        if params:
            url += f"?{params}"

        data_resp = _request("GET", url) or {}
        returns = data_resp.get("returns", [])
        if not returns:
            return {"returns": [], "_missing": True}

        # Map GSTR-3B shape → internal shape.
        mapped = []
        for r in returns:
            mapped.append({
                "period": r.get("ret_prd") or r.get("period") or "",
                "turnover": float(r.get("txval") or r.get("turnover") or 0),
                "filed_on_time": bool(r.get("filed_on_time", r.get("arn") is not None)),
                "nil_filing": bool(r.get("nil_filing", False)),
            })
        return {"returns": mapped}


class _SandboxConnector:
    """Generic stub for systems whose sandbox endpoint is not yet confirmed."""

    def __init__(self, system: SourceKind):
        self.system = system

    def fetch(self, msme_id: str, consent: ConsentArtefact, **kwargs) -> dict:
        raise NotImplementedError(
            f"Sandbox adapter for {self.system.value!r} not yet wired — "
            "IDBI sandbox endpoint contract not confirmed post-hackathon. "
            f"Flip CREDSIGHT_ADAPTER_{self.system.value.upper()}=synthetic to use synthetic data."
        )


_REGISTRY: dict[str, Any] = {
    "aa":     _AAConnector(),
    "gst":    _GSTConnector(),
    "upi":    _SandboxConnector(SourceKind.UPI),
    "epfo":   _SandboxConnector(SourceKind.EPFO),
    "bureau": _SandboxConnector(SourceKind.BUREAU),
}


def get(system: str) -> Any:
    if system not in _REGISTRY:
        raise ValueError(f"Unknown sandbox system {system!r}. Valid: {sorted(_REGISTRY)}")
    return _REGISTRY[system]
