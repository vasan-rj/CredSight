"""Shared knowledge types. PolicyClause is what `knowledge.search` returns and what the
audit rationale cites (every retrieved clause is referenced — the grounding rule,
ref-doc 02). ClauseLink + KnowledgeGraph are the P3 graph layer."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PolicyClause:
    ref: str          # citable id, e.g. "working-capital-eligibility#unsecured-limit"
    title: str
    text: str
    source: str       # source document filename
    page: int | None = None
    score: float = 0.0  # retrieval relevance (for ranking/telemetry; not shown to MSME)


@dataclass(frozen=True)
class ClauseLink:
    source_ref: str
    target_ref: str
    weight: float          # Jaccard similarity ∈ [0,1]
    reason: str            # "shared_terms" | "dedup_candidate"


@dataclass
class KnowledgeGraph:
    nodes: dict[str, PolicyClause]       # ref → clause
    edges: list[ClauseLink] = field(default_factory=list)
    communities: dict[str, list[str]] = field(default_factory=dict)  # label → [ref, ...]
    dedup_candidates: list[tuple[str, str]] = field(default_factory=list)
    built_at: str = ""

    def neighbors(self, ref: str) -> list[str]:
        """Direct graph neighbors of `ref` (undirected)."""
        return [
            e.target_ref if e.source_ref == ref else e.source_ref
            for e in self.edges
            if ref in (e.source_ref, e.target_ref)
        ]
