"""MCP server: ingestion tools — one per external data system (ref-doc 05).

Tools (read-only, consent-scoped):
  aa_fetch_statements, gst_fetch_returns, upi_fetch_txns, epfo_fetch, bureau_fetch

Each wraps the connector layer, so the same tool serves synthetic data now and IDBI
sandbox APIs later — a config flip (CREDSIGHT_ADAPTER_*), not a code change. Synthetic
data must be generated first (`credsight-gen-data`).

Run: `credsight-mcp-ingestion` (stdio transport) or `python -m credsight.mcp_servers.ingestion_server`.

The tool bodies delegate to module-level logic functions so they're unit-testable without
spawning a server.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .common import fetch_source

mcp = FastMCP("credsight-ingestion")


# --- logic (testable) -----------------------------------------------------

def aa_fetch_statements(msme_id: str, consent_id: str, scope: list[str]) -> dict:
    """Account Aggregator: bank statements (balances, inflows/outflows, bounces)."""
    return fetch_source("aa", msme_id, consent_id, scope)


def gst_fetch_returns(msme_id: str, consent_id: str, scope: list[str]) -> dict:
    """GST returns: turnover trend, filing punctuality, input-output."""
    return fetch_source("gst", msme_id, consent_id, scope)


def upi_fetch_txns(msme_id: str, consent_id: str, scope: list[str]) -> dict:
    """UPI/QR transaction history: counts, payers, seasonality, fraud flags."""
    return fetch_source("upi", msme_id, consent_id, scope)


def epfo_fetch(msme_id: str, consent_id: str, scope: list[str]) -> dict:
    """EPFO: active employees, contribution continuity (scale/formality proxy)."""
    return fetch_source("epfo", msme_id, consent_id, scope)


def bureau_fetch(msme_id: str, consent_id: str, scope: list[str]) -> dict:
    """Bureau: existing obligations, DPD (used when present; never required for NTC)."""
    return fetch_source("bureau", msme_id, consent_id, scope)


# --- MCP tool registration ------------------------------------------------

mcp.tool()(aa_fetch_statements)
mcp.tool()(gst_fetch_returns)
mcp.tool()(upi_fetch_txns)
mcp.tool()(epfo_fetch)
mcp.tool()(bureau_fetch)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
