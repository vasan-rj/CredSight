"""API smoke/regression tests. Exercise the real pipeline through HTTP (no mocks)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from credsight.api.app import app  # noqa: E402

client = TestClient(app)
LAKSHMI = "APP-LAKSHMI-001"


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_portfolio_has_demo_msmes():
    rows = client.get("/api/portfolio").json()
    names = {r["name"] for r in rows}
    assert "Lakshmi Stores" in names
    for r in rows:
        assert 300 <= r["composite"] <= 900
        assert 0.0 <= r["confidence"] <= 1.0


def test_hitl_shape_matches_frontend():
    h = client.get(f"/api/applications/{LAKSHMI}/hitl").json()
    assert set(h) == {"app_id", "reasons", "explanation", "score", "recommendation"}
    assert set(h["score"]) == {"app_id", "model_version", "dimensions", "composite",
                               "confidence", "shap"}
    assert "cash_flow_health" in h["score"]["dimensions"]


def test_explanation_is_faithful_to_drivers():
    # The explanation must reference the model's actual top SHAP driver (governance guard).
    h = client.get(f"/api/applications/{LAKSHMI}/hitl").json()
    top = h["score"]["shap"][0]["feature"].replace("_", " ")
    assert top in h["explanation"].lower()


def test_unknown_app_404():
    assert client.get("/api/applications/NOPE/hitl").status_code == 404


def test_rest_tool_score():
    # score_model.predict exposed as a normal REST tool.
    fv = {"app_id": "T1", "features": {"inflow_regularity": 0.9, "gst_filing_punctuality": 0.95},
          "n_sources": 3, "months_history": 12, "cross_source_agreement": 1.0}
    r = client.post("/api/tools/score", json=fv).json()
    assert 300 <= r["composite"] <= 900
    assert "dimensions" in r and "shap" in r


def test_rest_tool_knowledge():
    s = client.post("/api/tools/knowledge/search",
                    json={"query": "unsecured working capital limit score band", "segment": "micro"}).json()
    assert s["clauses"], "GBrain should return cited clauses for a relevant query"
    assert "working-capital-eligibility" in s["sources"]
    assert all("ref" in c and "text" in c for c in s["clauses"])


def test_decision_flow_appends_audit():
    before = client.get(f"/api/applications/MSME0002/audit").json()
    out = client.post("/api/applications/MSME0002/decision",
                      json={"decision": "approve", "reason": "test"}).json()
    assert out["ok"] and out["status"] == "approved"
    after = client.get(f"/api/applications/MSME0002/audit").json()
    types = [e["event_type"] for e in after]
    assert len(after) > len(before)
    assert "human_decision" in types
    assert "action" in types  # approval triggers the (logged) offer action
