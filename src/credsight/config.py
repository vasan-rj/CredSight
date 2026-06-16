"""Central configuration. Reads from environment (.env). Single source of truth for
adapter modes, HITL thresholds, model ids, and paths — so 'synthetic -> sandbox' is a
config flip, never a code change (PRD §9, ref-doc 05)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


AdapterMode = str  # "synthetic" | "sandbox"


@dataclass(frozen=True)
class HITLThresholds:
    """The parameter that shapes how much autonomy the bank's risk appetite allows
    (PRD §17 open question). A case interrupts to a human when any condition trips."""

    amount_threshold: float = float(_env("CREDSIGHT_HITL_AMOUNT_THRESHOLD", "200000"))
    confidence_floor: float = float(_env("CREDSIGHT_HITL_CONFIDENCE_FLOOR", "0.5"))


@dataclass(frozen=True)
class Config:
    # Connector modes — one per external system, flipped independently.
    adapters: dict[str, AdapterMode] = field(
        default_factory=lambda: {
            "aa": _env("CREDSIGHT_ADAPTER_AA", "synthetic"),
            "gst": _env("CREDSIGHT_ADAPTER_GST", "synthetic"),
            "upi": _env("CREDSIGHT_ADAPTER_UPI", "synthetic"),
            "epfo": _env("CREDSIGHT_ADAPTER_EPFO", "synthetic"),
            "bureau": _env("CREDSIGHT_ADAPTER_BUREAU", "synthetic"),
            "ocen": _env("CREDSIGHT_ADAPTER_OCEN", "synthetic"),
            "los": _env("CREDSIGHT_ADAPTER_LOS", "synthetic"),
        }
    )

    # LLM models — orchestration/reasoning/explanation ONLY. Never scoring.
    model_routing: str = _env("CREDSIGHT_MODEL_ROUTING", "anthropic:claude-haiku-4-5-20251001")
    model_reasoning: str = _env("CREDSIGHT_MODEL_REASONING", "anthropic:claude-sonnet-4-6")

    score_model_version: str = _env("CREDSIGHT_SCORE_MODEL_VERSION", "v0")
    hitl: HITLThresholds = field(default_factory=HITLThresholds)

    # Knowledge brain backend:
    #   "lexical"  — dependency-free incremental lexical indexer (default)
    #   "pgvector" — real semantic retrieval: sentence-transformer embeddings + pgvector
    #                store + cocoindex-memoized incremental embedding
    knowledge_backend: str = _env("CREDSIGHT_KNOWLEDGE_BACKEND", "lexical")
    # Postgres (pgvector) for the pgvector knowledge backend.
    knowledge_db_url: str = _env(
        "CREDSIGHT_KNOWLEDGE_DB_URL", "postgresql://credsight:credsight@localhost:5433/credsight"
    )
    embedding_model: str = _env("CREDSIGHT_EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    data_dir: Path = Path(_env("CREDSIGHT_DATA_DIR", "./data/synthetic"))
    database_url: str = _env("DATABASE_URL", "postgresql://localhost:5432/credsight")

    idbi_sandbox_base_url: str = _env("IDBI_SANDBOX_BASE_URL", "")
    idbi_sandbox_api_key: str = _env("IDBI_SANDBOX_API_KEY", "")

    def adapter_mode(self, system: str) -> AdapterMode:
        return self.adapters.get(system, "synthetic")


config = Config()
