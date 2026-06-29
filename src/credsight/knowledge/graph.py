"""Clause graph for GBrain (P3). Builds a weighted, undirected graph over PolicyClauses
using shared-term Jaccard similarity, detects connected-component communities, and flags
near-duplicate clauses across documents.

Persistence: `save_graph` writes a compact JSON to var/knowledge/graph.json so the dream
cycle's output survives across process restarts. `load_graph` returns that dict for the
API endpoint — the raw JSON is enough for visualisation; callers that need the typed
KnowledgeGraph call `build_graph` directly."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .index import _tokens
from .models import ClauseLink, KnowledgeGraph, PolicyClause

_LINK_THRESHOLD = 0.06   # min Jaccard to create an edge (tuned for short policy clauses)
_DEDUP_THRESHOLD = 0.45  # Jaccard above which two cross-doc clauses are dedup candidates
_GRAPH_PATH = Path("var") / "knowledge" / "graph.json"


# ── similarity ────────────────────────────────────────────────────────────────

def _term_bag(clause: PolicyClause) -> Counter:
    return Counter(_tokens(clause.title + " " + clause.text))


def _jaccard(a: Counter, b: Counter) -> float:
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    inter = sum(min(a.get(k, 0), b.get(k, 0)) for k in keys)
    union = sum(max(a.get(k, 0), b.get(k, 0)) for k in keys)
    return inter / union if union else 0.0


# ── Union-Find (connected components) ────────────────────────────────────────

def _make_parent(n: int) -> list[int]:
    return list(range(n))


def _find(parent: list[int], x: int) -> int:
    while parent[x] != x:
        parent[x] = parent[parent[x]]  # path halving
        x = parent[x]
    return x


def _union(parent: list[int], x: int, y: int) -> None:
    parent[_find(parent, x)] = _find(parent, y)


# ── graph builder ─────────────────────────────────────────────────────────────

def build_graph(clauses: list[PolicyClause]) -> KnowledgeGraph:
    """Build clause graph from a flat list of PolicyClauses.

    Edges: any pair with Jaccard >= LINK_THRESHOLD.
    Communities: connected components, labelled by majority source document.
    Dedup candidates: cross-doc pairs with Jaccard >= DEDUP_THRESHOLD."""
    if not clauses:
        return KnowledgeGraph(nodes={}, built_at=datetime.now(timezone.utc).isoformat())

    bags = [_term_bag(c) for c in clauses]
    edges: list[ClauseLink] = []
    dedup_candidates: list[tuple[str, str]] = []

    for i in range(len(clauses)):
        for j in range(i + 1, len(clauses)):
            sim = _jaccard(bags[i], bags[j])
            cross_doc = clauses[i].source != clauses[j].source
            if sim >= _DEDUP_THRESHOLD and cross_doc:
                dedup_candidates.append((clauses[i].ref, clauses[j].ref))
            if sim >= _LINK_THRESHOLD:
                reason = "dedup_candidate" if (sim >= _DEDUP_THRESHOLD and cross_doc) else "shared_terms"
                edges.append(ClauseLink(
                    source_ref=clauses[i].ref,
                    target_ref=clauses[j].ref,
                    weight=round(sim, 3),
                    reason=reason,
                ))

    # Connected components → communities
    idx = {c.ref: i for i, c in enumerate(clauses)}
    parent = _make_parent(len(clauses))
    for e in edges:
        if e.source_ref in idx and e.target_ref in idx:
            _union(parent, idx[e.source_ref], idx[e.target_ref])

    root_to_refs: dict[int, list[str]] = {}
    for c in clauses:
        root = _find(parent, idx[c.ref])
        root_to_refs.setdefault(root, []).append(c.ref)

    # Label each community by the ref of its highest-degree clause (unique, readable).
    # For a singleton, that's just the clause's own ref.
    edge_counts: Counter = Counter()
    for e in edges:
        edge_counts[e.source_ref] += 1
        edge_counts[e.target_ref] += 1

    communities: dict[str, list[str]] = {}
    for refs in root_to_refs.values():
        hub = max(refs, key=lambda r: (edge_counts[r], r))  # highest-degree; alpha tie-break
        communities[hub] = refs

    return KnowledgeGraph(
        nodes={c.ref: c for c in clauses},
        edges=edges,
        communities=communities,
        dedup_candidates=dedup_candidates,
        built_at=datetime.now(timezone.utc).isoformat(),
    )


# ── graph-aware retrieval expansion ──────────────────────────────────────────

def expand_with_neighbors(refs: list[str], graph: KnowledgeGraph, hops: int = 1) -> list[str]:
    """Breadth-first expansion: original refs first, then their graph neighbors up to `hops`."""
    seen: set[str] = set(refs)
    frontier: list[str] = list(refs)
    for _ in range(hops):
        next_frontier: list[str] = []
        for r in frontier:
            for nbr in graph.neighbors(r):
                if nbr not in seen:
                    seen.add(nbr)
                    next_frontier.append(nbr)
        frontier = next_frontier
    return list(refs) + [r for r in frontier]


# ── persistence ───────────────────────────────────────────────────────────────

def save_graph(graph: KnowledgeGraph) -> None:
    _GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "built_at": graph.built_at,
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "nodes": [
            {"ref": c.ref, "title": c.title, "source": c.source}
            for c in graph.nodes.values()
        ],
        "edges": [
            {"source": e.source_ref, "target": e.target_ref,
             "weight": e.weight, "reason": e.reason}
            for e in graph.edges
        ],
        "communities": graph.communities,
        "dedup_candidates": [list(p) for p in graph.dedup_candidates],
    }
    _GRAPH_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_graph() -> dict | None:
    """Load the persisted graph JSON (from the last organize cycle), or None."""
    if not _GRAPH_PATH.exists():
        return None
    return json.loads(_GRAPH_PATH.read_text(encoding="utf-8"))
