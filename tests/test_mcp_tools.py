"""MCP tool servers — ingestion (consent-scoped, synthetic-backed) and action (idempotent).
Tests call the tool logic functions directly (no server spawn needed)."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("mcp")

from credsight.data.generators.archetypes import Archetype  # noqa: E402
from credsight.data.generators.generate import generate_bundle  # noqa: E402
from credsight.mcp_servers import action_server as act  # noqa: E402
from credsight.mcp_servers import ingestion_server as ing  # noqa: E402


def test_ingestion_refuses_out_of_consent_scope():
    # GST not in the consent scope -> connector refuses before any read (FR-3).
    with pytest.raises(PermissionError):
        ing.gst_fetch_returns("MSME_X", "c1", scope=["bank_aa"])


def test_ingestion_returns_synthetic_source(tmp_path, monkeypatch):
    # Point the synthetic adapter at a tmp data dir and seed one bundle there.
    from credsight.connectors import synthetic as syn

    monkeypatch.setattr(syn, "config", type("C", (), {"data_dir": tmp_path})())
    (tmp_path / "MSME_T.json").write_text(
        json.dumps(generate_bundle("MSME_T", "t", Archetype.STRONG, 1), default=str)
    )

    out = ing.aa_fetch_statements("MSME_T", "c1", scope=["bank_aa", "gst", "upi"])
    assert "accounts" in out
    assert out["accounts"] and out["accounts"][0]["txns"]


def test_action_offer_is_idempotent():
    a = act.ocen_create_offer("APP1", 250000, 18.0, 24)
    b = act.ocen_create_offer("APP1", 250000, 18.0, 24)
    assert a == b
    assert a["offer_id"] == "OFFER-APP1"
    assert a["idempotency_key"] == "APP1"


def test_action_los_create_application():
    out = act.los_create_application("MSME1", "approved", idempotency_key="APP1")
    assert out["application_ref"] == "LOS-APP1"
    assert out["decision"] == "approved"
