"""End-to-end tests for the real third-party integrations: Docling (PDF parse),
deepagents (LLM supervisor build), cocoindex+pgvector (semantic knowledge backend).

Each is guarded: skipped cleanly when its optional dependency or infra (Postgres on
CREDSIGHT_KNOWLEDGE_DB_URL) is absent, so the core suite still runs on a minimal install."""

from __future__ import annotations

import pytest


# --- Docling: real PDF -> Markdown ---------------------------------------
def test_docling_parses_pdf(tmp_path):
    pytest.importorskip("docling")
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    pdf = tmp_path / "policy.pdf"
    c = canvas.Canvas(str(pdf))
    c.drawString(72, 720, "Working capital eligibility for micro enterprises.")
    c.save()

    from credsight.knowledge.parse import parse_document

    doc = parse_document(pdf)
    assert "working capital" in doc.markdown.lower()


# --- deepagents: real supervisor compiles --------------------------------
def test_deepagents_supervisor_builds():
    pytest.importorskip("deepagents")
    from credsight.agents.orchestrator import build_deep_agent

    agent = build_deep_agent()
    assert type(agent).__name__ == "CompiledStateGraph"
    # The LLM-drivable tools exist and the deterministic layer works without a key.
    from credsight.agents import llm_tools

    assert {t.name for t in llm_tools.ALL_TOOLS} >= {"ingest", "score", "create_offer"}
    out = llm_tools.ingest.invoke({"app_id": "T", "archetype": "strong", "seed": 1})
    assert "Ingested" in out


# --- cocoindex + pgvector: real semantic retrieval -----------------------
def _pg_available() -> bool:
    try:
        import psycopg  # noqa: F401

        from credsight.config import config

        psycopg.connect(config.knowledge_db_url, connect_timeout=2).close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _pg_available(), reason="pgvector Postgres not reachable")
def test_pgvector_semantic_search_and_incremental():
    pytest.importorskip("sentence_transformers")
    pytest.importorskip("cocoindex")
    from pathlib import Path

    from credsight.knowledge.pgvector_backend import PgVectorBackend

    base = Path(__file__).resolve().parents[1] / "src" / "credsight" / "knowledge" / "policies"
    b = PgVectorBackend([base])
    b.refresh()
    assert len(b.all_clauses()) > 0

    # Semantic hit with no lexical overlap routes to the thin-file guidance.
    hits = b.search("how do you handle a borrower with almost no credit history?")
    assert hits and hits[0].source == "thin-file-ntc"
    assert 0.0 <= hits[0].score <= 1.0
