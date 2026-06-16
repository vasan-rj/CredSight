"""Orchestrator entrypoints.

Two layers, by design:
  1. The WORKING orchestrator is the LangGraph StateGraph in agents/graph.py, driven via
     agents/run.py (start_assessment / resume_assessment). It runs the full workflow with
     a durable checkpointer and a real human-in-the-loop interrupt — no LLM/API key needed,
     because the credit path is deterministic by design.
  2. The OPTIONAL deepagents supervisor (build_deep_agent below) adds LLM planning
     (write_todos) + subagents on top. It needs Python >=3.11 and an ANTHROPIC_API_KEY;
     when absent, use the graph — it is the substance.
"""

from __future__ import annotations

from .graph import build_graph
from .run import resume_assessment, start_assessment

__all__ = ["build_graph", "start_assessment", "resume_assessment", "build_deep_agent"]


def build_deep_agent(checkpointer: bool = True):
    """Construct the deepagents LLM supervisor (ref-doc 07): planning (write_todos) +
    single-purpose subagents over the real CredSight tools, with the human-in-the-loop
    interrupt on the money-moving `create_offer` action.

    Returns a compiled LangGraph agent. Building needs the `agent` extra (Python >=3.11);
    *running* it additionally needs an ANTHROPIC_API_KEY. The deterministic LangGraph
    orchestrator (build_graph / start_assessment) remains the key-free runtime — this is
    the LLM-planning layer on top, and it still never computes the score (it calls the
    `score` tool, which calls the versioned model)."""
    try:
        from deepagents import create_deep_agent
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "deepagents is not installed (needs Python >=3.11 and the 'agent' extra)."
        ) from e

    from ..config import config
    from . import llm_tools
    from .prompts import (
        ACTION_PROMPT,
        INGESTION_PROMPT,
        ORCHESTRATOR_PROMPT,
        RECONCILIATION_PROMPT,
        SCORING_PROMPT,
    )

    # Single-purpose subagents with least-privilege tool scopes (ref-doc 03).
    subagents = [
        {"name": "consent_ingestion", "description": "Pull + normalise alternate data with consent.",
         "system_prompt": INGESTION_PROMPT, "tools": llm_tools.INGEST_TOOLS},
        {"name": "reconciliation_enrichment", "description": "Cross-validate, flag fraud, derive features.",
         "system_prompt": RECONCILIATION_PROMPT, "tools": llm_tools.RECON_TOOLS},
        {"name": "scoring_decisioning", "description": "Compute the score + policy-checked recommendation.",
         "system_prompt": SCORING_PROMPT, "tools": llm_tools.SCORE_TOOLS},
        {"name": "offer_action", "description": "Execute the approved offer. Post-approval only.",
         "system_prompt": ACTION_PROMPT, "tools": llm_tools.ACTION_TOOLS},
    ]

    return create_deep_agent(
        model=config.model_reasoning,
        tools=llm_tools.ALL_TOOLS,
        system_prompt=ORCHESTRATOR_PROMPT,
        subagents=subagents,
        # HITL: pause before the money-moving action until a human approves (the trust gate).
        interrupt_on={"create_offer": True},
        checkpointer=checkpointer,
    )
