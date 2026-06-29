"""S5 — Sandbox connector smoke tests.

Run with:  pytest -m sandbox tests/test_sandbox_connectors.py
Requires:  pip install pytest

Tests do NOT call real IDBI endpoints. AA and GST connectors are tested with
urllib mock patches. Unimplemented connectors (UPI/EPFO/Bureau) must raise
NotImplementedError — this is a deliberate contract, not a missing feature.
"""

from __future__ import annotations

import io
import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("credsight")

from credsight.connectors.sandbox import get
from credsight.data.schema import ConsentArtefact, SourceKind


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def aa_consent() -> ConsentArtefact:
    return ConsentArtefact(
        consent_id="TEST-CONSENT-001",
        scope=[SourceKind.BANK_AA, SourceKind.GST],
        granted_on=date.today(),
        valid_until=date(2027, 1, 1),
    )


@pytest.fixture
def gst_consent() -> ConsentArtefact:
    return ConsentArtefact(
        consent_id="TEST-CONSENT-002",
        scope=[SourceKind.GST],
        granted_on=date.today(),
        valid_until=date(2027, 1, 1),
    )


# ── Unimplemented connectors raise NotImplementedError ────────────────────────

@pytest.mark.sandbox
@pytest.mark.parametrize("system", ["upi", "epfo", "bureau"])
def test_unimplemented_connectors_raise(system: str, aa_consent: ConsentArtefact):
    """UPI/EPFO/Bureau must raise NotImplementedError — contract, not a bug."""
    # Give a consent that covers anything so PermissionError doesn't fire first.
    full_consent = ConsentArtefact(
        consent_id="TEST-FULL",
        scope=list(SourceKind),
        granted_on=date.today(),
        valid_until=date(2027, 1, 1),
    )
    connector = get(system)
    with pytest.raises(NotImplementedError, match="sandbox endpoint"):
        connector.fetch("MSME-TEST", full_consent)


# ── Consent gate ──────────────────────────────────────────────────────────────

@pytest.mark.sandbox
def test_aa_connector_refuses_out_of_scope(gst_consent: ConsentArtefact):
    """AA connector must refuse when bank_aa is not in consent scope."""
    connector = get("aa")
    with pytest.raises(PermissionError, match="bank_aa"):
        connector.fetch("MSME-TEST", gst_consent)


@pytest.mark.sandbox
def test_gst_connector_refuses_out_of_scope(aa_consent: ConsentArtefact):
    """GST connector must refuse when gst is not in consent scope."""
    gst_only_consent = ConsentArtefact(
        consent_id="TEST-BANK-ONLY",
        scope=[SourceKind.BANK_AA],  # no GST
        granted_on=date.today(),
        valid_until=date(2027, 1, 1),
    )
    connector = get("gst")
    with pytest.raises(PermissionError, match="gst"):
        connector.fetch("MSME-TEST", gst_only_consent)


# ── AA connector with mocked HTTP ─────────────────────────────────────────────

@pytest.mark.sandbox
def test_aa_connector_maps_response(aa_consent: ConsentArtefact):
    """AA connector maps sandbox response → dict with accounts + txns."""
    mock_consent_resp = {"consent_id": "SANDBOX-CONSENT-001"}
    mock_data_resp = {
        "accounts": [{"account_ref": "ACC001", "avg_monthly_balance": 85000.0}],
        "txns": [
            {"txn_date": "2026-01-05", "amount": 22000.0, "counterparty": "UPI/CR/GPay"},
            {"txn_date": "2026-01-10", "amount": -8000.0, "counterparty": "NACH/EMI"},
        ],
    }

    responses = [
        _mock_http_response(mock_consent_resp),
        _mock_http_response(mock_data_resp),
    ]

    with patch("credsight.connectors.sandbox._base_url", return_value="https://sandbox.test"), \
         patch("credsight.connectors.sandbox._api_key", return_value="test-key"), \
         patch("urllib.request.urlopen", side_effect=responses):
        connector = get("aa")
        result = connector.fetch("MSME-TEST", aa_consent)

    assert "accounts" in result
    assert "txns" in result
    assert len(result["accounts"]) == 1
    assert len(result["txns"]) == 2
    assert result.get("_missing") is not True


@pytest.mark.sandbox
def test_aa_connector_partial_response_marks_missing(aa_consent: ConsentArtefact):
    """Empty response (MSME not found in sandbox) → _missing=True, no exception."""
    empty_consent = {"consent_id": "SANDBOX-EMPTY"}
    empty_data    = {"accounts": [], "txns": []}

    responses = [
        _mock_http_response(empty_consent),
        _mock_http_response(empty_data),
    ]

    with patch("credsight.connectors.sandbox._base_url", return_value="https://sandbox.test"), \
         patch("credsight.connectors.sandbox._api_key", return_value="test-key"), \
         patch("urllib.request.urlopen", side_effect=responses):
        connector = get("aa")
        result = connector.fetch("MSME-TEST", aa_consent)

    assert result.get("_missing") is True
    assert result["accounts"] == []


# ── GST connector with mocked HTTP ───────────────────────────────────────────

@pytest.mark.sandbox
def test_gst_connector_maps_returns(gst_consent: ConsentArtefact):
    """GST connector maps GSTR-3B shape → list of period/turnover/filed_on_time dicts."""
    mock_resp = {
        "returns": [
            {"ret_prd": "012026", "txval": 450000, "arn": "AA29012026123", "nil_filing": False},
            {"ret_prd": "022026", "txval": 480000, "arn": "AA29022026456", "nil_filing": False},
        ]
    }

    with patch("credsight.connectors.sandbox._base_url", return_value="https://sandbox.test"), \
         patch("credsight.connectors.sandbox._api_key", return_value="test-key"), \
         patch("urllib.request.urlopen", return_value=_mock_http_response(mock_resp)):
        connector = get("gst")
        result = connector.fetch("29AAKCS9398D1ZF", gst_consent, gstin="29AAKCS9398D1ZF")

    assert "returns" in result
    returns = result["returns"]
    assert len(returns) == 2
    assert returns[0]["period"] == "012026"
    assert returns[0]["turnover"] == 450000.0
    assert returns[0]["filed_on_time"] is True


@pytest.mark.sandbox
def test_gst_connector_404_returns_empty(gst_consent: ConsentArtefact):
    """404 from sandbox (GSTIN not found) → empty returns, no exception."""
    import urllib.error

    with patch("credsight.connectors.sandbox._base_url", return_value="https://sandbox.test"), \
         patch("credsight.connectors.sandbox._api_key", return_value="test-key"), \
         patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
             url=None, code=404, msg="Not Found", hdrs=None, fp=None  # type: ignore[arg-type]
         )):
        connector = get("gst")
        result = connector.fetch("INVALID-GSTIN", gst_consent, gstin="INVALID-GSTIN")

    assert result.get("_missing") is True
    assert result.get("returns") == []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_http_response(data: dict):
    """Return a context-manager mock that yields a response with JSON body."""
    raw = json.dumps(data).encode()
    resp = MagicMock()
    resp.read.return_value = raw
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp
