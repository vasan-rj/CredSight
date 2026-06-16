"""MCP server: action tools — the write side (ref-doc 05). These move/commit things in
the bank's systems, so they are the most permissioned surface: the orchestrator only
invokes them AFTER the HITL approval clears, and they are idempotent (FR-19/20/21).

Tools:
  ocen_create_offer, los_create_application, los_request_docs, notify_msme

Idempotency: a given key (application id) always yields the same offer/application ref, so
a retry never double-books. Stubs return standards-shaped payloads; real OCEN/LOS wiring
slots in on sandbox access without changing the tool contracts.

Run: `credsight-mcp-action` (stdio) or `python -m credsight.mcp_servers.action_server`.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("credsight-action")


# --- logic (testable) -----------------------------------------------------

def ocen_create_offer(application_id: str, amount: float, rate: float, tenor: int) -> dict:
    """Generate a standards-shaped (OCEN/ULI) credit offer. Idempotent by application_id."""
    return {
        "offer_id": f"OFFER-{application_id}",
        "idempotency_key": application_id,
        "amount": amount,
        "rate": rate,
        "tenor_months": tenor,
        "status": "created",
    }


def los_create_application(msme_id: str, decision: str, idempotency_key: str) -> dict:
    """Open/advance the loan application in the LOS. Idempotent by idempotency_key."""
    return {
        "application_ref": f"LOS-{idempotency_key}",
        "msme_id": msme_id,
        "decision": decision,
        "status": "opened",
    }


def los_request_docs(application_ref: str, doc_list: list[str]) -> dict:
    """Request missing documents for an application."""
    return {"ok": True, "application_ref": application_ref, "requested": doc_list}


def notify_msme(msme_id: str, message: str) -> dict:
    """Notify the MSME of status / what to upload."""
    return {"ok": True, "msme_id": msme_id, "message": message}


# --- MCP tool registration ------------------------------------------------

mcp.tool()(ocen_create_offer)
mcp.tool()(los_create_application)
mcp.tool()(los_request_docs)
mcp.tool()(notify_msme)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
