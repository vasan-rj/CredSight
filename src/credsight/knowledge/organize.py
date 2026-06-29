"""GBrain 'dream cycle' — the real organize() implementation (P3).

Called by brain.organize() and by the nightly cron (POST /api/knowledge/organize).
Steps:
  1. Pull all_clauses() from the backend (lexical or pgvector).
  2. Build the clause graph (Jaccard edges, connected-component communities).
  3. Persist to var/knowledge/graph.json for the API and the next search.
  4. Return a summary dict.

The cycle never mutates the source Markdown — it only writes the derived graph JSON.
Dedup candidates are surfaced for human review, not auto-merged."""

from __future__ import annotations

from .graph import build_graph, save_graph


def run_organize_cycle(backend) -> dict:
    """Run the dream cycle over the given knowledge backend. Returns a summary dict
    suitable for the API response and the audit trail."""
    clauses = backend.all_clauses()
    if not clauses:
        return {
            "clauses": 0, "edges": 0, "communities": 0,
            "dedup_candidates": 0, "built_at": None,
        }

    graph = build_graph(clauses)
    save_graph(graph)

    return {
        "clauses": len(graph.nodes),
        "edges": len(graph.edges),
        "communities": len(graph.communities),
        "community_detail": graph.communities,
        "dedup_candidates": len(graph.dedup_candidates),
        "dedup_pairs": graph.dedup_candidates,
        "built_at": graph.built_at,
        # For the frontend GraphView — typed arrays
        "nodes": [
            {"ref": c.ref, "title": c.title, "source": c.source}
            for c in graph.nodes.values()
        ],
        "edge_list": [
            {"source": e.source_ref, "target": e.target_ref,
             "weight": e.weight, "reason": e.reason}
            for e in graph.edges
        ],
    }
