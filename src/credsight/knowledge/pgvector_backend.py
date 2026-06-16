"""Real semantic knowledge backend — sentence-transformer embeddings stored in Postgres
pgvector, with incremental embedding memoized by CocoIndex.

This is the genuine vector-retrieval backend (selected with
CREDSIGHT_KNOWLEDGE_BACKEND=pgvector). It implements the same interface as the lexical
index (refresh / search / all_clauses), so brain.py and every caller are unchanged.

CocoIndex's role here is its core value — **incremental, memoized recompute**: the embed
step is wrapped in `@cocoindex.fn(memo=True)`, so unchanged clause text is never re-embedded
(memoized by content hash). A content-hash column in Postgres is the durable incremental
gate across process restarts; CocoIndex memoization avoids recompute within a run.

Requirements (met by the project's dedicated container): Postgres with the `vector`
extension (CREDSIGHT_KNOWLEDGE_DB_URL) and an embedding model (CREDSIGHT_EMBEDDING_MODEL).
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import cocoindex

from ..config import config
from .index import _chunk  # reuse the same clause-chunking as the lexical backend
from .models import PolicyClause
from .parse import parse_document

_TABLE = "policy_clauses"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(config.embedding_model)


@lru_cache(maxsize=1)
def _dim() -> int:
    m = _model()
    getter = getattr(m, "get_embedding_dimension", None) or m.get_sentence_embedding_dimension
    return int(getter())


# Module-level — stable __qualname__ for CocoIndex memo persistence across runs.
# Skips re-embedding unchanged clause text (memoized by content hash via CocoIndex).
@cocoindex.fn(memo=True)
def _embed(text: str) -> list[float]:
    return _model().encode([text])[0].tolist()


class PgVectorBackend:
    """Semantic retrieval backend. Interface-compatible with LexicalIndex."""

    def __init__(self, dirs: list[Path]):
        self._dirs = dirs
        self._conn = None
        self._ensure_schema()

    # --- connection / schema ---
    def _connect(self):
        if self._conn is None or self._conn.closed:
            import psycopg
            from pgvector.psycopg import register_vector

            self._conn = psycopg.connect(config.knowledge_db_url, autocommit=True)
            self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            register_vector(self._conn)
        return self._conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {_TABLE} ("
            "ref text PRIMARY KEY, source text, title text, body text, "
            f"content_hash text, embedding vector({_dim()}))"
        )

    # --- incremental refresh ---
    def refresh(self) -> None:
        """Re-chunk source dirs and upsert; embed only clauses whose content changed."""
        import numpy as np

        conn = self._connect()
        seen: set[str] = set()
        existing = {r[0]: r[1] for r in conn.execute(
            f"SELECT ref, content_hash FROM {_TABLE}").fetchall()}

        for d in self._dirs:
            if not d.exists():
                continue
            for p in sorted(d.glob("*.md")):
                doc = parse_document(p)
                for c in _chunk(doc.markdown, p.stem):
                    seen.add(c.ref)
                    h = _hash(c.text)
                    if existing.get(c.ref) == h:
                        continue  # unchanged -> skip embed (incremental gate)
                    vec = np.array(_embed(c.text))  # memoized embed
                    conn.execute(
                        f"INSERT INTO {_TABLE} (ref, source, title, body, content_hash, embedding) "
                        "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (ref) DO UPDATE SET "
                        "source=EXCLUDED.source, title=EXCLUDED.title, body=EXCLUDED.body, "
                        "content_hash=EXCLUDED.content_hash, embedding=EXCLUDED.embedding",
                        (c.ref, c.source, c.title, c.text, h, vec),
                    )
        # Drop clauses whose source doc/heading no longer exists.
        stale = set(existing) - seen
        if stale:
            conn.execute(f"DELETE FROM {_TABLE} WHERE ref = ANY(%s)", (list(stale),))

    # --- search ---
    def search(self, query: str, segment: str | None = None, k: int = 3) -> list[PolicyClause]:
        import numpy as np

        self.refresh()
        conn = self._connect()
        q = np.array(_embed(f"{query} {segment}" if segment else query))
        rows = conn.execute(
            f"SELECT ref, title, body, source, 1 - (embedding <=> %s) AS sim "
            f"FROM {_TABLE} ORDER BY embedding <=> %s LIMIT %s",
            (q, q, k),
        ).fetchall()
        return [PolicyClause(ref=r[0], title=r[1], text=r[2], source=r[3], score=round(r[4], 3))
                for r in rows]

    def all_clauses(self) -> list[PolicyClause]:
        conn = self._connect()
        rows = conn.execute(f"SELECT ref, title, body, source FROM {_TABLE}").fetchall()
        return [PolicyClause(ref=r[0], title=r[1], text=r[2], source=r[3]) for r in rows]
