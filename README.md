# CredSight

**Agentic credit underwriting infrastructure for credit-invisible MSMEs.**

750 million small businesses worldwide pay on time — in cash, across UPI, through informal networks — and remain invisible to the banking system. Traditional credit models require a formal footprint they were never given. CredSight changes the denominator.

CredSight is a production-grade agentic underwriting OS that ingests every available signal — Account Aggregator, GST, UPI, EPFO, bureau — reconciles them for internal consistency, runs a deterministic interpretable scoring model, and surfaces a **Financial Health Card**: a single explainable score a loan officer can act on. The agent pauses at the credit decision. A human approves. The log is immutable.

---

## Design principles

Three invariants that are non-negotiable in any deployment:

**1 — The LLM never touches the credit decision.**
A calibrated XGBoost model scores. SHAP explains which drivers moved the needle. LLMs orchestrate the workflow, reconcile cross-source anomalies, and phrase the narrative — but they are faithfulness-gated: the explanation may reference only the model's actual top SHAP drivers and retrieved policy clauses. On any failure the system closes to a deterministic, faithful-by-construction template. Without an API key the decision still runs. Without SHAP the decision still runs. The credit path has zero dependency on a hosted model being available.

**2 — The human-in-the-loop pause is the product.**
Every loan above the threshold, every rejection, every low-confidence assessment hits a durable interrupt. The underwriter sees the full SHAP-grounded rationale, the cross-source reconciliation, and the policy clauses that apply. Their identity, decision, and reason are written to the immutable audit trail before any action executes downstream. This is not a checkbox — it is what makes the system deployable inside a regulated institution.

**3 — Synthetic now, sandbox later, production after — same code.**
Every external system sits behind a typed connector interface. `SyntheticAdapter` serves generated data today. `SandboxAdapter` calls the bank's sandbox APIs on integration. `LiveAdapter` goes to production. The swap is a per-connector `.env` flag. No agent code changes. No test rewrites.

---

## How it works

```
  MSME applies
       │
       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  Consent & Ingestion                                        │
  │  AA · GST · UPI · EPFO · Bureau → canonical/{id}.json      │
  │  Partial success allowed — missing source lowers confidence │
  └─────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  Reconciliation & Enrichment                 THE MOAT       │
  │  Cross-check turnover: GST ↔ bank ↔ UPI                    │
  │  Flag circular UPI, pre-application spike, EPFO anomaly     │
  │  Every flag is rule-backed — LLM triages, never invents     │
  │  → features/{id}.json · recon/{id}.md                      │
  └─────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  Scoring                                  DETERMINISTIC     │
  │  5 interpretable dimensions → XGBoost composite 300–900     │
  │  SHAP per-driver attribution                                │
  │  Thin-file confidence ∈ [0,1] travels with the score        │
  └─────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  HITL Gate                              DURABLE INTERRUPT   │
  │  Fires on: amount > threshold · reject · confidence < floor │
  │  Blocks all downstream action until human decision recorded │
  └─────────────────────────────────────────────────────────────┘
       │                    │
       ▼ approved           ▼ rejected / info requested
  ┌──────────────┐    ┌─────────────────────────────────────────┐
  │  Offer &     │    │  Audit Trail                            │
  │  Action      │    │  Immutable append-only · every step     │
  │  OCEN · LOS  │    │  cited · regulatorily legible           │
  └──────────────┘    └─────────────────────────────────────────┘
```

The orchestrator is a **LangGraph StateGraph** with a durable checkpointer. Working state lives in a virtual filesystem (`var/canonical`, `var/features`, `var/recon`, `var/audit`) — not in message history. Each subagent runs in an isolated context window and reaches external systems only through permissioned MCP tool servers.

---

## The scoring model

Five interpretable dimensions, each 0–100, composited into a 300–900 band:

| Dimension | Weight | Primary sources |
|---|---|---|
| Cash-flow health | 30% | Bank statements (AA), UPI/QR |
| GST & turnover signal | 20% | GST returns |
| Banking discipline | 20% | Bank statements (AA) |
| Business vintage & stability | 15% | GST registration, business profile |
| Obligation load & formality | 15% | AA liabilities, EPFO, bureau |

Each sub-score uses transparent monotonic transforms independently explainable to a loan officer. The composite is a calibrated XGBoost (isotonic/Platt) for ranking power. Both views — GBM composite and weighted-dimension — are returned on every assessment.

A **thin-file confidence score ∈ [0,1]** is computed from: number of sources present, months of history available, and cross-source agreement. It travels with every score, drives HITL routing, and is shown to the underwriter. Presenting a score *and how much to trust it* is a material differentiator.

---

## Financial Health Card

The MSME-facing surface — and the underwriter's primary tool:

- Composite score ring (300–900) with confidence indicator
- Five dimension gauges with plain-language driver labels
- SHAP waterfall — which factors lifted or pulled the score
- **Path to Bankability** — concrete, ranked actions to reach the next credit band
- HITL pause banner with full rationale when human review is required

The card renders from the deterministic scoring output. No LLM is in the render path.

---

## Quickstart

```bash
# Python 3.12 via uv (recommended)
uv venv && source .venv/bin/activate
pip install -e ".[dev]"

# Config — synthetic mode by default (no real PII, no real money)
cp .env.sandbox.example .env
# fill ANTHROPIC_API_KEY to enable LLM-authored narratives (optional)

# Seed the synthetic MSME portfolio (4 archetypes: thin-file, strong, stressed, fraud)
python -m credsight.service.demo_seed

# Run the eval harness (AUC/KS, explanation faithfulness, band stability)
pytest -q

# Start the backend (port 8000)
credsight-api
# or: uvicorn credsight.api.app:app --reload --port 8000
```

```bash
# Frontend (separate terminal)
cd frontend && npm install && npm run dev
# → http://localhost:5173
```

To run the UI without a backend: set `USE_MOCK = true` in `frontend/src/api.ts`.

---

## Demo path

The golden path that exercises every system layer:

1. **Applicants tab** — select Lakshmi (thin-file kirana) or the fraud archetype
2. **Health Card** — composite + 5 gauges + confidence renders; Path to Bankability below
3. **Underwriter Console** — HITL interrupt fires automatically; amber badge on tab; full rationale shown
4. **Approve / Override / Request Info** — decision captured immutably; action agent runs
5. **Audit Trail** — every step cited with source, timestamp, and actor identity
6. **Learning Loop** — override patterns surfaced as calibration signals for the risk team
7. **Knowledge Graph** — policy clauses and learned fraud patterns the agent retrieves at decision time

The two moments that close the narrative: a Financial Health Card for someone the system used to reject, and the agent stopping for a human with a complete explanation before touching any loan system.

---

## API reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness |
| `GET` | `/api/portfolio` | MSME portfolio summary |
| `POST` | `/api/orchestrator/run` | Run the full assessment graph; returns score, recommendation, HITL payload if triggered |
| `POST` | `/api/orchestrator/resume` | Resume a paused run with an underwriter decision |
| `GET` | `/api/applications/{id}/audit` | Immutable audit trail for an application |
| `POST` | `/api/tools/score` | Direct call to `score_model.predict` |
| `POST` | `/api/tools/knowledge/search` | Policy retrieval from the knowledge brain |
| `POST` | `/api/tools/knowledge/capture` | Write a learned pattern back to the knowledge brain |
| `POST` | `/api/upload/msme` | Upload raw bank/GST statements for ad-hoc assessment |

---

## MCP tool surfaces

External-system integrations run as separate MCP tool servers — typed, permissioned, independently deployable, swappable synthetic↔sandbox without agent-code changes.

**Ingestion** (`credsight-mcp-ingestion`) — read-only, consent-scoped:

| Tool | Description |
|---|---|
| `aa_fetch_statements` | Account Aggregator — bank statements |
| `gst_fetch_returns` | GST returns (GSTR-1, GSTR-3B) |
| `upi_fetch_txns` | UPI/QR transaction history |
| `epfo_fetch` | EPFO contribution records |
| `bureau_fetch` | Bureau pull (CIBIL/Experian stub) |

Consent scope is enforced at the boundary — a fetch for a source outside the consent artefact is refused before any read.

**Action** (`credsight-mcp-action`) — write, post-approval only, idempotent:

| Tool | Description |
|---|---|
| `ocen_create_offer` | Create OCEN-compliant loan offer |
| `los_create_application` | Open application in LOS |
| `los_request_docs` | Trigger document checklist |
| `notify_msme` | Send status notification to borrower |

All action tools are idempotent by application ID — same key returns the same offer/application reference, no double-booking.

---

## Knowledge brain

`src/credsight/knowledge/` implements a self-organising policy knowledge layer:

```
Policy PDFs / Markdown
       │
       ▼ Docling (PDF → structured Markdown, page/bbox metadata preserved)
       │
       ▼ CocoIndex (incremental chunk → embed → upsert; memoized — unchanged clauses never re-embedded)
       │
       ▼ GBrain (Postgres + pgvector hybrid search index; MCP access)
       │
  agents call knowledge.search at decision time
  agents call knowledge.capture to write learnings back
```

Every retrieved clause carries a citable `ref` (e.g. `working-capital-eligibility#unsecured-limit-by-score-band`). The grounding rule: every policy clause cited in the recommendation must appear in the audit trail. The faithfulness check enforces this before the explanation is returned.

Two backends:

- **`lexical`** (default) — dependency-free TF-IDF hybrid search. No Postgres, no embeddings. Runs anywhere.
- **`pgvector`** — sentence-transformer embeddings (`all-MiniLM-L6-v2`) in Postgres + pgvector, cosine search, CocoIndex-memoized incremental embedding. Set `CREDSIGHT_KNOWLEDGE_BACKEND=pgvector`.

---

## Postgres + pgvector (full stack)

```bash
docker run -d --name credsight-postgres \
  -e POSTGRES_USER=credsight \
  -e POSTGRES_PASSWORD=credsight \
  -e POSTGRES_DB=credsight \
  -p 5433:5432 pgvector/pgvector:pg15

pip install -e ".[dev,agent,knowledge,mcp]"
CREDSIGHT_KNOWLEDGE_BACKEND=pgvector credsight-api
```

---

## Synthetic archetypes

Four internally-consistent MSME profiles used as regression fixtures on every run:

| Archetype | Profile | Reconciliation behaviour |
|---|---|---|
| `thin_file` | UPI + partial GST only | Low confidence; routes to HITL |
| `strong` | Consistent GST / bank / UPI growth | Auto-approves at sufficient amount |
| `stressed` | Declining turnover, bounces, rising obligations | HITL on borderline; reject on severe |
| `fraud` | Circular UPI, pre-application inflow spike | Reconciliation flags; HITL required |

Synthetic data is internally consistent per MSME — the same shop's GST turnover, bank inflows, and UPI volume agree within tolerance. This is what makes the reconciliation layer meaningful, not cosmetic.

---

## Install layers

```bash
pip install -e ".[dev]"              # core + tests (Python 3.10+)
pip install -e ".[agent]"            # LangGraph orchestrator + deepagents (Python 3.11+)
pip install -e ".[knowledge]"        # Docling + CocoIndex + pgvector
pip install -e ".[mcp]"              # MCP tool servers
pip install -e ".[dev,agent,knowledge,mcp]"  # full stack
```

The deterministic core and full test suite run with only `pydantic`, `python-dotenv`, and `pytest`. Heavy dependencies (`xgboost`, `shap`, `deepagents`, `langgraph`, `mcp`, `docling`) are optional and gated by extra.

---

## Stack

| Layer | Technology |
|---|---|
| Agent harness | LangGraph (durable execution, checkpointing, streaming, HITL interrupts) |
| Supervisor | Deep Agents (`deepagents`) — planning + subagent delegation |
| Decisioning | XGBoost + SHAP (Python, versioned, never an LLM) |
| Integrations | MCP servers — one per external system |
| Knowledge brain | Docling → CocoIndex → GBrain (Postgres + pgvector) |
| API | FastAPI + uvicorn |
| Frontend | React + TypeScript + Vite + Tailwind |
| Observability | LangSmith + OpenTelemetry |
| Primary store | PostgreSQL |
| Models | Claude Sonnet 4.6 (orchestration/reconciliation), Claude Haiku 4.5 (routing/classification) |

---

## Repo layout

```
src/credsight/
  config.py              # adapter modes, HITL thresholds, model IDs, paths
  connectors/            # base interface + SyntheticAdapter + SandboxAdapter
  scoring/               # THE DETERMINISTIC CORE — no LLM ever touches this
    dimensions.py        # five interpretable 0–100 sub-scores
    confidence.py        # thin-file confidence [0,1]
    model.py             # versioned composite (300–900) + score_model.predict
    pathways.py          # Path to Bankability — ranked improvement actions
    eval.py              # CI eval harness (AUC/KS, faithfulness, stability)
  knowledge/             # Docling → CocoIndex → GBrain pipeline
  governance/            # HITL gate, immutable audit log, faithfulness check, learning loop
  agents/                # LangGraph orchestrator + subagent specs + prompts
  api/                   # FastAPI application + all endpoints
  service/               # domain models, pipeline runner, demo seed

frontend/src/
  components/
    HealthCard.tsx        # Financial Health Card + skeleton
    PathToBankability.tsx # Score improvement roadmap
    UnderwriterConsole.tsx # HITL decision surface
    AuditTrail.tsx        # Immutable audit viewer
    LearningLoop.tsx      # Override pattern surface for risk team
    GBrain.tsx            # Knowledge graph explorer
    UploadMSME.tsx        # Ad-hoc statement upload

tests/
  test_orchestrator.py
  test_e2e_demo_flows.py
  test_pathways.py
  test_sandbox_connectors.py
```

---

## License

MIT
