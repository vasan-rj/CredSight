# CredSight

**Agentic credit-underwriting OS that turns credit-invisible MSMEs into bankable borrowers.**
Built for **IDBI Innovate 2026 — Track 03 (Financial Inclusion / Digital Lending / Credit Decisioning)**.

CredSight runs the full underwriting workflow — **ingest → decide → act → log** — as a deep agent that takes real actions in the bank's tools, **pauses for a human at the credit decision**, and leaves an immutable audit trail. The human-facing surface is the **MSME Financial Health Card**; the substance underneath is a deterministic, explainable scoring core wrapped in an agentic harness with governance built in.

> **The LLM never computes the credit score or makes the credit decision.** A deterministic, versioned ML model (XGBoost + SHAP) decides; LLMs orchestrate, reconcile, and explain. That, plus the human-in-the-loop gate and immutable audit, is what makes it deployable in a bank.

## Docs

| Doc | What |
|---|---|
| `doc/prd.md` | Product requirements — the consolidated requirements view |
| `CLAUDE.md` | Working guide + non-negotiable invariants |
| `reference-docs/01`–`07` | The implementation reference pack (source of truth on any conflict) |

## Repo layout

```
src/credsight/
  config.py            # adapter modes, HITL thresholds, model ids, paths (synthetic<->sandbox flip)
  data/
    schema.py          # canonical normalised schema (the ingestion->scoring contract)
    generators/        # synthetic MSME data: 3 archetypes + fraud variant
  scoring/             # THE DETERMINISTIC CORE — no LLM ever touches this
    dimensions.py      # 5 interpretable 0-100 sub-scores
    confidence.py      # thin-file confidence [0,1]
    model.py           # versioned composite (300-900) + predict() = score_model.predict
    explain.py         # SHAP drivers (trained-model path)
    policy.py          # band -> eligible product/amount/rate/tenor
    eval.py            # CI eval harness (AUC/KS, faithfulness, stability)
  reconciliation/      # THE MOAT — cross-source checks + rule-backed fraud flags
  connectors/          # adapter seam: base interface + synthetic + sandbox stubs
  knowledge/           # GBrain access (Docling -> CocoIndex -> GBrain)
  governance/          # HITL gate + immutable audit log + faithfulness check
  agents/              # Deep Agents orchestrator + subagent contracts + prompts
  mcp_servers/         # MCP tool servers (one per external system)
tests/                 # deterministic-core + governance tests (run today, no network)
```

## Quickstart

```bash
# 1. Editable install with dev extras
pip install -e ".[dev]"

# 2. Configure (synthetic mode by default — no real PII, no real money)
cp .env.example .env        # fill ANTHROPIC_API_KEY when wiring agents

# 3. Generate synthetic data (3 archetypes + fraud, internally consistent per MSME)
credsight-gen-data -n 24

# 4. Train the calibrated XGBoost composite + SHAP (writes a gitignored artifact)
credsight-train                # optional — predict() falls back to the interpretable
                               # weighted-dimension composite if no artifact exists

# 5. Run the tests (deterministic core, feature pipeline, trained model, API)
pytest -q

# 6. Run the eval harness
credsight-eval

# 7. Run the backend API (real pipeline: score -> recommend -> HITL -> audit)
credsight-api                 # or: uvicorn credsight.api.app:app --reload --port 8000
```

## Running the full demo (two processes)

```bash
# Terminal 1 — backend (port 8000)
source .venv/bin/activate
credsight-api

# Terminal 2 — frontend (port 5173, proxies /api -> 8000)
cd frontend && npm run dev
```

Open http://localhost:5173. The four tabs are the golden path: Health Card → Underwriter Console (HITL) → Audit Trail → Portfolio. Scores are computed by the real deterministic model in `scoring/` — no LLM in the decision path. To run the UI without the backend, set `USE_MOCK = true` in `frontend/src/api.ts`.

### API endpoints

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | liveness |
| GET | `/api/portfolio` | `MsmeSummary[]` |
| GET | `/api/applications/{id}/hitl` | `HITLRequest` (score + recommendation + explanation) |
| GET | `/api/applications/{id}/audit` | `AuditEvent[]` (append-only log) |
| POST | `/api/applications/{id}/decision` | `{ ok, status }` — records the underwriter decision |
| POST | `/api/orchestrator/run` | drive a live run through the graph → HITL interrupt payload or auto-decision |
| POST | `/api/orchestrator/resume` | resume a paused run with the underwriter decision |

### Orchestrator

The orchestrator is a **LangGraph StateGraph** (`agents/graph.py`): `ingest → reconcile → score → gate → action`, with a durable checkpointer and a real **human-in-the-loop `interrupt()`** at the credit decision. State is offloaded to a virtual filesystem (`var/canonical`, `var/features`, `var/recon`, `var/audit`). It runs with **no API key** — the credit path is deterministic by design. The optional deepagents LLM planning/subagent supervisor (`agents/orchestrator.py:build_deep_agent`) needs Python ≥3.11 + the `agent` extra and sits on top.

**Explanations** (`agents/narrate.py`): the MSME-facing narrative is LLM-generated (Claude, via `ANTHROPIC_API_KEY`) but **faithfulness-gated** — the prompt may reference only the model's actual top SHAP drivers, and the output is checked before return; on any failure (no key, library/network error, unfaithful answer) it **fails closed** to a deterministic, faithful-by-construction template. The LLM never computes or alters the score — only phrases the explanation. Without a key, you get the template; the decision never waits on the LLM.

```bash
# install layers as needed
pip install -e ".[dev]"          # core + tests (Python 3.10+)
pip install -e ".[agent]"        # deepagents supervisor (Python 3.11+)
pip install -e ".[mcp,storage]"  # MCP servers + Postgres
```

> The core + tests run with only `pydantic`, `python-dotenv`, and `pytest` installed — the heavy deps (`xgboost`, `shap`, `deepagents`, `langgraph`, `mcp`) are needed only as their respective layers come online.

## Build order (core-first — see `doc/prd.md` §14)

1. Scoring service + reconciliation on synthetic data — **the substance and the moat** (✅ scaffolded; fill the TODOs days 3–6).
2. Ingestion + canonical schema; Health Card UI.
3. HITL gate + immutable audit log; Explainability — **the trust layer**.
4. Offer & Action; orchestrator + subagents on Deep Agents + LangGraph.
5. (If time) async monitoring agent.

## Tool surfaces

Tools are split by where the work lives:

**MCP tool servers** — external-system integrations, run as separate processes the agent connects to over stdio; typed, permissioned, swappable synthetic↔sandbox (needs the `mcp` extra):

| Server | Run | Tools |
|---|---|---|
| Ingestion (read-only, consent-scoped) | `credsight-mcp-ingestion` | `aa_fetch_statements`, `gst_fetch_returns`, `upi_fetch_txns`, `epfo_fetch`, `bureau_fetch` |
| Action (write, post-approval, idempotent) | `credsight-mcp-action` | `ocen_create_offer`, `los_create_application`, `los_request_docs`, `notify_msme` |

Ingestion tools enforce **consent scope at the boundary** — a fetch for a source outside the consent artefact is refused before any read. Action tools are **idempotent** (same key → same offer/application ref, no double-booking).

**Normal REST API tools** — in-process deterministic services that also back the UI:

| Method | Path | Tool |
|---|---|---|
| POST | `/api/tools/score` | `score_model.predict` — the deterministic scoring core |
| POST | `/api/tools/knowledge/search` | `knowledge.search` (GBrain-backed) |
| POST | `/api/tools/knowledge/capture` | `knowledge.capture` |

## Knowledge brain (GBrain)

`knowledge/` implements the **Docling → (index) → GBrain** pipeline (ref-doc 05):
- **parse** (`parse.py`) — Markdown is the source of truth; PDFs/DOCX go through Docling when the `knowledge` extra is installed (optional — heavy stack stays out of the core).
- **index** — pluggable backend (`config.knowledge_backend`):
  - `lexical` (default, `index.py`) — dependency-free incremental indexer: mtime-tracked, deterministic **hybrid lexical search** (TF-IDF over clause chunks). No Postgres/embeddings. Runs anywhere.
  - `pgvector` (`pgvector_backend.py`) — **real semantic retrieval**: sentence-transformer embeddings (`all-MiniLM-L6-v2`) stored in **Postgres + pgvector**, cosine search. Incremental via a content-hash gate + **CocoIndex `@fn(memo=True)`** memoized embedding (cocoindex's core value — unchanged clauses are never re-embedded). Needs the `knowledge` extra + the project Postgres container (`CREDSIGHT_KNOWLEDGE_DB_URL`). Same interface as lexical.
- **parse** also does **real PDF/DOCX → Markdown via Docling** (`knowledge/parse.py`, tested end-to-end) — drop policy PDFs in and they index.
- **brain** (`brain.py`) — agents **`search`** policy at decision time and **`capture`** learnings back (new Markdown clauses, searchable immediately). Seeded policy in `knowledge/policies/*.md`; captured learnings in `knowledge/learned/` (gitignored).

### Runtime + the third-party stack (Python 3.12)

deepagents, cocoindex, and Docling require **Python ≥3.11**; the project venv is **3.12** (via `uv`). The semantic backend uses a **dedicated Postgres container** (isolated from any other DB):

```bash
docker run -d --name credsight-postgres \
  -e POSTGRES_USER=credsight -e POSTGRES_PASSWORD=credsight -e POSTGRES_DB=credsight \
  -p 5433:5432 pgvector/pgvector:pg15

pip install -e ".[dev,agent,knowledge,mcp]"     # full stack (Python 3.11+)
CREDSIGHT_KNOWLEDGE_BACKEND=pgvector credsight-api
```

- **deepagents** supervisor: `agents.orchestrator.build_deep_agent()` builds a real compiled agent (planning + subagents + HITL `interrupt_on` `create_offer`); *running* it needs `ANTHROPIC_API_KEY`.
- **Docling**: `knowledge/parse.py` parses real PDFs (downloads OCR/layout models on first use).
- **cocoindex + pgvector**: `CREDSIGHT_KNOWLEDGE_BACKEND=pgvector` → semantic retrieval with cocoindex-memoized incremental embedding.

The orchestrator's scoring node retrieves the applicable clauses and **cites their refs in the recommendation + audit trail** — the grounding rule (never decide ungrounded). Every returned clause carries a citable `ref` like `working-capital-eligibility#unsecured-limit-by-score-band`.

Why the split: cross-system integrations belong behind MCP (typed, permissioned, separately deployable, synthetic↔sandbox); internal deterministic services are simplest as REST since they run in-process and the frontend calls them too.

## Synthetic ↔ sandbox

Every external system sits behind a connector interface (`connectors/`). `SyntheticAdapter` serves generated data now; `SandboxAdapter` calls IDBI's sandbox APIs on shortlist. The swap is a per-connector config flip in `.env` (`CREDSIGHT_ADAPTER_*`) — **no agent code changes**.

## Status

Synthetic-data build. All external integrations are adapter-mocked; no real PII, no real money movement. The architecture is designed so the sandbox swap is a config change, not a rewrite.
