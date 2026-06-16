"""Deep Agents orchestrator + specialist subagents (ref-doc 03). The orchestrator plans
with write_todos and delegates to single-purpose subagents via the `task` tool, each in
an isolated context window. Wire this AFTER the deterministic core works (ref-doc 02
§'The one thing to do first')."""
