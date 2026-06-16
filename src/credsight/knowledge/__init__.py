"""Agentic knowledge brain (ref-doc 05): Docling (parse policy docs) -> incremental index
-> GBrain (Markdown source of truth + searchable index). Agents read (knowledge.search) AND
write (knowledge.capture) — a brain, not a static index. Every retrieved clause is cited in
the audit rationale.

The index backend is pluggable (config.knowledge_backend):
  - "lexical"  — dependency-free incremental lexical indexer (index.py, default)
  - "pgvector" — semantic retrieval: sentence-transformer embeddings + Postgres pgvector,
    with CocoIndex-memoized incremental embedding (pgvector_backend.py)
The default lexical backend runs anywhere; pgvector adds real semantic search."""
