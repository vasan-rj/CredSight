"""Lightweight incremental lexical index over parsed Markdown — the default knowledge
backend. Dependency-free: no embedding model, no Postgres, no torch.

This backend:
- Chunks each doc by '## ' clause heading (precise, citable units).
- Builds a hybrid lexical index (term frequency x inverse document frequency) — real,
  deterministic retrieval.
- INCREMENTAL: tracks file mtimes and reprocesses only changed/new/removed docs on refresh.

For semantic retrieval over a larger corpus, set CREDSIGHT_KNOWLEDGE_BACKEND=pgvector
(pgvector_backend.py — sentence-transformer embeddings + Postgres pgvector, with
CocoIndex-memoized incremental embedding). Both implement the same interface
(refresh / search / all_clauses)."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .models import PolicyClause
from .parse import parse_document

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "is", "are", "be", "by",
    "with", "as", "at", "not", "that", "this", "than", "from", "within", "must", "should",
    "may", "where", "which", "such", "into", "per", "its", "it",
}
_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS and len(t) > 2]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


@dataclass
class _Chunk:
    ref: str
    title: str
    text: str
    source: str
    terms: Counter  # term frequencies


def _chunk(markdown: str, source: str) -> list[_Chunk]:
    """Split a doc into clause chunks by '## ' headings."""
    chunks: list[_Chunk] = []
    cur_title, cur_lines = None, []

    def flush():
        if cur_title is None:
            return
        body = "\n".join(cur_lines).strip()
        if not body:
            return
        chunks.append(_Chunk(
            ref=f"{source}#{_slug(cur_title)}", title=cur_title, text=body, source=source,
            terms=Counter(_tokens(cur_title + " " + body)),
        ))

    for line in markdown.splitlines():
        if line.startswith("## "):
            flush()
            cur_title, cur_lines = line[3:].strip(), []
        elif cur_title is not None:
            cur_lines.append(line)
    flush()
    return chunks


class LexicalIndex:
    """Incremental hybrid-lexical index over Markdown source dirs. Implements the
    knowledge-backend interface (refresh / search / all_clauses). For semantic retrieval,
    use the pgvector backend (see module docstring)."""

    def __init__(self, dirs: list[Path]):
        self._dirs = dirs
        self._chunks: list[_Chunk] = []
        self._mtimes: dict[str, float] = {}
        self._idf: dict[str, float] = {}

    def refresh(self) -> None:
        """Reprocess only changed/new docs; drop removed ones; recompute IDF if anything moved."""
        current: dict[str, float] = {}
        for d in self._dirs:
            if d.exists():
                for p in sorted(d.glob("*.md")):
                    current[str(p)] = p.stat().st_mtime

        changed = {p for p, m in current.items() if self._mtimes.get(p) != m}
        removed = set(self._mtimes) - set(current)
        if not changed and not removed:
            return

        # Keep chunks from untouched docs; reparse only changed; drop removed.
        dirty_stems = {Path(p).stem for p in changed | removed}
        keep = [c for c in self._chunks if c.source not in dirty_stems]
        for p in changed:
            doc = parse_document(Path(p))
            keep.extend(_chunk(doc.markdown, Path(p).stem))
        self._chunks = keep
        self._mtimes = current
        self._recompute_idf()

    def _recompute_idf(self) -> None:
        n = len(self._chunks) or 1
        df: Counter = Counter()
        for c in self._chunks:
            df.update(set(c.terms))
        self._idf = {t: math.log(1 + n / (1 + dfi)) for t, dfi in df.items()}

    def _score(self, query_terms: list[str], chunk: _Chunk) -> float:
        return sum(chunk.terms.get(t, 0) * self._idf.get(t, 0.0) for t in query_terms)

    def search(self, query: str, segment: str | None = None, k: int = 3) -> list[PolicyClause]:
        self.refresh()
        q = _tokens(query) + (_tokens(segment) if segment else [])
        if not q:
            return []
        scored = [(self._score(q, c), c) for c in self._chunks]
        scored = [(s, c) for s, c in scored if s > 0]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            PolicyClause(ref=c.ref, title=c.title, text=c.text, source=c.source,
                         score=round(s, 3))
            for s, c in scored[:k]
        ]

    def all_clauses(self) -> list[PolicyClause]:
        self.refresh()
        return [PolicyClause(ref=c.ref, title=c.title, text=c.text, source=c.source)
                for c in self._chunks]


# Back-compat alias (older imports referenced KnowledgeIndex).
KnowledgeIndex = LexicalIndex
