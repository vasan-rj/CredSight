"""Application service — runs the deterministic pipeline (score -> recommend -> HITL ->
audit) and holds application state. The API layer (credsight.api) is a thin HTTP shell
over this. The Deep Agents orchestrator (agents/) will drive the same service once wired;
until then this is a direct, testable pipeline so the demo runs end-to-end."""
