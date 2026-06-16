"""Connector layer. Every external system sits behind a clean interface with two
implementations — SyntheticAdapter (now) and SandboxAdapter (IDBI, on shortlist).
Agents call the MCP tool and never know which adapter is behind it (ref-doc 05).

  Agent --(MCP call)--> Connector Interface --> {Synthetic | Sandbox} --> source

The active adapter is chosen per-system by config.adapter_mode(system) — a config flip,
not a code change. This is what makes 'deployment-ready' true rather than a slide."""

from .base import DataConnector, get_connector

__all__ = ["DataConnector", "get_connector"]
