"""Tool surfaces, split by where the work lives (ref-doc 02/05):

MCP tool servers — external-system integrations, run as separate processes the agent
connects to over stdio; typed, permissioned, swappable synthetic<->sandbox:
  - ingestion_server: aa_fetch_statements, gst_fetch_returns, upi_fetch_txns, epfo_fetch,
    bureau_fetch   (read-only, consent-scoped)
  - action_server:    ocen_create_offer, los_create_application, los_request_docs,
    notify_msme       (write, post-approval, idempotent)

Normal REST API tools (credsight.api) — in-process deterministic services that also back
the UI, exposed as plain HTTP endpoints:
  - POST /api/tools/score            (score_model.predict — the deterministic core)
  - POST /api/tools/knowledge/search (knowledge.search — GBrain-backed)
  - POST /api/tools/knowledge/capture(knowledge.capture)

Why the split: cross-system integrations belong behind MCP (typed, permissioned, swappable,
separately deployable); internal deterministic services are simplest as REST since they're
in-process and the frontend calls them too.
"""
