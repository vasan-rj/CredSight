"""Shared knowledge types. PolicyClause is what `knowledge.search` returns and what the
audit rationale cites (every retrieved clause is referenced — the grounding rule,
ref-doc 02)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyClause:
    ref: str          # citable id, e.g. "working-capital-eligibility#unsecured-limit"
    title: str
    text: str
    source: str       # source document filename
    page: int | None = None
    score: float = 0.0  # retrieval relevance (for ranking/telemetry; not shown to MSME)
