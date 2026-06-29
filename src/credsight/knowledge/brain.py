"""GBrain — the agentic knowledge base (ref-doc 05). Markdown is the operator-owned source
of truth; an incremental index makes it searchable; agents read (`search`) policy at
decision time AND write (`capture`) new learnings back, which a nightly `organize` cycle
would tidy. That read-and-write loop is what makes it a brain, not a static index.

Backed by:
  - knowledge/policies/   — seeded policy/scheme Markdown (Docling output goes here too)
  - knowledge/learned/    — learnings captured by the agents at runtime

The index backend is pluggable (config.knowledge_backend):
  - "lexical"  (default) — our dependency-free incremental lexical indexer (index.py)
  - "pgvector"           — semantic retrieval: sentence-transformer embeddings + pgvector
                           store, with CocoIndex-memoized incremental embedding (pgvector_backend.py)
Both implement the same interface, so the rest of the brain is backend-agnostic.

Both source dirs are indexed together, so a captured fraud pattern becomes searchable on
the next call. Every clause returned carries a citable `ref` for the audit rationale."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..config import config
from .models import PolicyClause

_BASE = Path(__file__).parent
_POLICIES = _BASE / "policies"
_LEARNED = _BASE / "learned"
_CAPTURE_FILE = _LEARNED / "captured-learnings.md"


def _make_backend():
    backend = config.knowledge_backend
    if backend == "pgvector":
        from .pgvector_backend import PgVectorBackend

        return PgVectorBackend([_POLICIES, _LEARNED])
    from .index import LexicalIndex

    return LexicalIndex([_POLICIES, _LEARNED])


_INDEX = _make_backend()


def search(query: str, segment: str | None = None, k: int = 3,
           graph_expand: bool = False) -> list[PolicyClause]:
    """Retrieve policy clauses applicable to this query/segment (no context stuffing).

    graph_expand=True: after top-k retrieval, expand 1 hop through the persisted clause
    graph so related clauses (e.g. fraud signals linked to turnover corroboration) surface
    alongside the direct hits. Silently no-ops if no graph has been built yet (run organize
    first). Returns [] when nothing is relevant — callers must treat empty as 'ungrounded'.
    """
    results = _INDEX.search(query, segment, k=k)
    if not graph_expand or not results:
        return results

    from .graph import expand_with_neighbors, load_graph
    from .models import KnowledgeGraph

    raw = load_graph()
    if raw is None:
        return results

    # Rebuild a lightweight graph from the persisted JSON (nodes + edges only — no bags).
    from .models import ClauseLink
    nodes = {n["ref"]: PolicyClause(ref=n["ref"], title=n["title"], text="", source=n["source"])
             for n in raw.get("nodes", [])}
    edges = [ClauseLink(source_ref=e["source"], target_ref=e["target"],
                        weight=e["weight"], reason=e["reason"])
             for e in raw.get("edges", [])]
    graph = KnowledgeGraph(nodes=nodes, edges=edges)

    refs = [c.ref for c in results]
    expanded = expand_with_neighbors(refs, graph, hops=1)
    extra_refs = [r for r in expanded if r not in set(refs)]
    if not extra_refs:
        return results

    # Fetch full text for neighbor clauses and append (lower rank — they're bonus context).
    all_clauses = {c.ref: c for c in _INDEX.all_clauses()}
    neighbors = [all_clauses[r] for r in extra_refs if r in all_clauses]
    return results + neighbors[:max(1, k // 2)]


def capture(note: str, tags: list[str] | None = None) -> bool:
    """Write a derived learning (e.g. a newly observed fraud pattern) back into GBrain as a
    new clause. It becomes searchable immediately (the index reprocesses the changed file)."""
    tags = tags or []
    _LEARNED.mkdir(parents=True, exist_ok=True)
    if not _CAPTURE_FILE.exists():
        _CAPTURE_FILE.write_text("# Captured learnings (agent-written)\n\n", encoding="utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    title = (note[:60] + "…") if len(note) > 60 else note
    entry = f"## {title}\n\n{note}\n\n_tags: {', '.join(tags) or 'none'} · captured {stamp}_\n\n"
    with _CAPTURE_FILE.open("a", encoding="utf-8") as fh:
        fh.write(entry)
    _INDEX.refresh()  # incremental: only the changed learnings file is reprocessed
    return True


def organize() -> dict:
    """Nightly 'dream' cycle — build the clause graph, detect communities and dedup
    candidates, persist graph.json. Returns a summary dict for the API + audit trail."""
    from .organize import run_organize_cycle
    return run_organize_cycle(_INDEX)
