"""CredSight — agentic credit-underwriting OS for credit-invisible MSMEs.

Build order (core-first, per reference-docs/03 §"Implementation order"):
  1. scoring/        — the deterministic decisioning core (the substance)
  2. reconciliation/ — the hard last mile (the moat)
  3. data/           — synthetic data generators (build first 2 days)
  4. connectors/     — MCP adapter interfaces (synthetic <-> sandbox)
  5. agents/         — Deep Agents orchestrator + subagents
  6. governance/     — HITL gate + immutable audit log (the trust layer)
"""

__version__ = "0.1.0"
