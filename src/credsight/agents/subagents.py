"""Subagent configs for Deep Agents (ref-doc 03 §worked example). Each is single-purpose
with least-privilege tool + file scopes. The orchestrator spawns them via the built-in
`task` tool; each runs in an isolated context window.

These are plain dicts matching the deepagents subagent shape so they stay declarative and
reviewable. Tool names map to the MCP tool servers in credsight.mcp_servers.

TODO(days 15-17): bind real MCP tool handles + permission rules when wiring the
orchestrator; the contracts here are the source of truth."""

from __future__ import annotations

from . import prompts

INGESTION = {
    "name": "consent_ingestion",
    "description": "Pull and normalise an MSME's alternate data with consent. Call first.",
    "system_prompt": prompts.INGESTION_PROMPT,
    "tools": ["aa.fetch_statements", "gst.fetch_returns", "upi.fetch_txns", "epfo.fetch",
              "bureau.fetch"],
    # read-only on data tools, scoped to consent; write to canonical/
}

RECONCILIATION = {
    "name": "reconciliation_enrichment",
    "description": "Cross-validate + enrich canonical data; flag fraud/inconsistencies.",
    "system_prompt": prompts.RECONCILIATION_PROMPT,
    "tools": ["knowledge.search"],
    # read canonical/, write features/ + recon/; read-only knowledge
}

SCORING = {
    "name": "scoring_decisioning",
    "description": "Compute the multidimensional health score + a policy-checked "
                   "recommendation. Call after features are ready.",
    "system_prompt": prompts.SCORING_PROMPT,
    "tools": ["score_model.predict", "knowledge.search"],
    # read features/; no action tools, no money movement
}

EXPLAINABILITY = {
    "name": "explainability",
    "description": "Explain the score/decision for MSME, underwriter, and audit log.",
    "system_prompt": prompts.EXPLAINABILITY_PROMPT,
    "tools": [],  # LLM over provided structured inputs; faithfulness-checked
}

ACTION = {
    "name": "offer_action",
    "description": "Execute the approved offer in the bank's systems. Post-approval only.",
    "system_prompt": prompts.ACTION_PROMPT,
    "tools": ["ocen.create_offer", "los.create_application", "los.request_docs",
              "notify.msme"],
    # the ONLY subagent allowed action tools, and only when status == approved
}

MONITORING = {
    "name": "monitoring_early_warning",
    "description": "Async: watch onboarded MSMEs for emerging stress and re-score.",
    "system_prompt": prompts.MONITORING_PROMPT,
    "tools": ["aa.fetch_statements", "gst.fetch_returns", "upi.fetch_txns",
              "score_model.predict"],
    # read-only; alerts are recommendations, never automated actions
}

ALL_SUBAGENTS = [INGESTION, RECONCILIATION, SCORING, EXPLAINABILITY, ACTION, MONITORING]
