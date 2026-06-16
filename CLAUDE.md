# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**CredSight** — an agentic credit-underwriting OS for the **IDBI Innovate 2026 hackathon, Track 03 (Financial Inclusion / Digital Lending)**. It turns credit-invisible MSMEs into bankable borrowers by running the full **ingest → decide → act → log** workflow with a human-in-the-loop approval gate. The human-facing surface is the **MSME Financial Health Card**; underneath is a deep agent that takes real actions in the bank's tools and logs every step for the risk team and regulator.

The repo is currently **greenfield**: only `reference-docs/` exists (the implementation reference pack). Read those docs before building — they are the binding contract. Order: `00-README.md` (index) → `01-idea-agentic-reframe.md` (the conceptual contract) → `02-architecture.md` (read before writing code) → `03`–`07` per task.

## Non-negotiable invariants (these define the project; do not violate)

1. **The LLM never computes the credit score or makes the credit decision.** A deterministic, versioned ML model (XGBoost + SHAP) decides. LLMs only orchestrate, reconcile, and explain. A bank cannot deploy a black-box credit decision — this is the whole pitch.
2. **Guardrails are the product, not overhead.** HITL approval gate, scoped least-privilege permissions, immutable audit log, explainability, and sandboxing are the deliverable, not extras. The HITL pause + audit trail is the demo centrepiece.
3. **Own the workflow, not a step.** The defensible thing is running onboarding-to-monitoring end to end. Scoring is one node in a graph the agent owns.
4. **Synthetic now → IDBI sandbox later is a config swap, not a rewrite.** Every external system sits behind a clean connector interface (`SyntheticAdapter` | `SandboxAdapter`) exposed as an MCP tool. Agents call the MCP tool and never know which adapter is behind it. Keep this seam clean.
5. **Build the deterministic core first.** Scoring service + reconciliation logic on synthetic data come before any agent wiring. The agentic shell wraps a core that already works.

## Architecture (the big picture)

A single **deep agent orchestrator** (Deep Agents `create_deep_agent` on the LangGraph runtime) plans with `write_todos` and delegates to single-purpose **specialist subagents** via the built-in `task` tool, each in an isolated context window. Subagents reach external systems only through permissioned **MCP tool servers**, store working state in the **virtual filesystem** (not the prompt), and the credit decision **pauses at a HITL interrupt**.

Subagent pipeline (`03-agent-specs.md` has full per-agent contracts — I/O, tools, permissions, guardrails):

1. **Orchestrator** — plans, sequences, owns the HITL pause. Routing only, never credit math, no action tools.
2. **Consent & Ingestion** — AA consent → parallel fetch of bank/GST/UPI/EPFO/bureau → normalise to canonical schema → write `canonical/{app_id}.json`. Read-only. Partial success allowed (missing source → flag + lower confidence).
3. **Reconciliation & Enrichment** *(the hard last mile — invest here)* — cross-check turnover across GST vs bank vs UPI, resolve disagreements with documented rules, flag fraud/gaming, tag seasonality, derive features → `features/{app_id}.json` + `recon/{app_id}.md`. Every flag is rule-backed; LLM triages/explains rule hits, never invents them.
4. **Scoring & Decisioning** — calls the deterministic `score_model.predict`, checks against credit policy from the knowledge brain, emits a recommendation. Cannot execute loan actions; out-of-policy forces human review.
5. **Explainability** — turns SHAP drivers + policy refs into plain-language + structured audit rationale → `audit/{app_id}.log`. **Faithfulness check**: text may reference only the model's actual top SHAP drivers and retrieved clauses; fails closed to a template.
6. **HITL Approval Gate** — Deep Agents interrupt on `amount > threshold` OR `recommendation == reject` OR `confidence < floor` OR `out_of_policy`. Captures human identity + reason. No downstream action runs until cleared.
7. **Offer & Action** *(only post-approval)* — generates OCEN/ULI offer, opens loan in LOS, requests docs. The **only** subagent with action/write permissions. Idempotency key per application.
8. **Monitoring & Early-Warning** *(async, optional)* — periodic re-ingest + re-score for stress. Read-only; alerts are recommendations, never automated actions.

### Three storage tiers (a feature to showcase, not an implementation detail)
- **Virtual filesystem** (backend = LangGraph store) — per-run working memory: `canonical/`, `features/`, `recon/`, `audit/`. Keeps context lean; gives the demo a visible agent scratchpad.
- **Long-term memory store** — cross-run: MSME profiles, prior assessments, underwriter override history.
- **Knowledge brain (GBrain)** — shared, self-organising domain knowledge (policy clauses, sector norms, learned fraud patterns) that agents read **and write**.

### The knowledge brain (replaces generic RAG)
**Docling** (parse policy PDFs → structured Markdown/JSON with page/bbox metadata for citable grounding) → **CocoIndex** (incremental chunk/embed/upsert into vector store + KG; reprocesses only changed docs) → **GBrain** (Markdown source of truth, Postgres/PGLite hybrid search index, MCP access). Agents use `knowledge.search` at decision time and `knowledge.capture` to write learnings back. Grounding rule: retrieve only the policy clauses applying to this applicant's segment, and cite every retrieved clause in the audit rationale.

## The scoring model (the substance — `04-scoring-model.md`)

Five interpretable dimensions, each 0–100, weighted into a composite scaled to a **300–900** band:

| Dimension | Weight | Sources |
|---|---|---|
| Cash-flow health | 30% | Bank (AA), UPI/QR |
| GST & turnover signal | 20% | GST |
| Banking discipline | 20% | Bank (AA) |
| Business vintage & stability | 15% | GST, profile |
| Obligation load / formality | 15% | AA, EPFO, bureau |

- Per-dimension sub-scores: transparent monotonic transforms / lightweight models (each independently explainable).
- Composite: calibrated XGBoost (isotonic/Platt) for ranking power; show both the GBM and the weighted-dimension view.
- A **thin-file confidence ∈ [0,1]** (from #sources, months of history, cross-source agreement) travels with every score and routes low-confidence cases to the HITL gate. This is a differentiator — present a score *and how much to trust it*.
- Weights are config; calibrate against synthetic labels and document any change (auditability).

## MCP tool contracts (`05-data-and-integrations.md` has the typed sketches)

- **Ingestion (read-only, consent-scoped):** `aa.fetch_statements`, `gst.fetch_returns`, `upi.fetch_txns`, `epfo.fetch`, `bureau.fetch`
- **Decisioning:** `score_model.predict`, `knowledge.search`, `knowledge.capture`
- **Action (write, permissioned, post-approval, idempotent):** `ocen.create_offer`, `los.create_application`, `los.request_docs`, `notify.msme`

## Synthetic data (build in the first 2 days, store generators in the repo)

Three base archetypes + a fraud variant, **internally consistent per MSME** (same shop's GST turnover, bank inflows, UPI volume should roughly agree — inconsistent synthetic data makes the demo look broken and breaks the reconciliation tolerance checks):
- **thin-file micro** (UPI + partial GST only), **strong** (consistent GST/bank/UPI growth), **stressed** (declining turnover, bounces, rising obligations), **fraud** (circular UPI, pre-application inflow spike — demos the reconciliation flag).

Keep these three as fixed **regression archetypes** (thin-file, strong, stressed) re-run on every change. The eval harness (run in CI from day one) measures: decision quality (AUC/KS vs synthetic labels, calibration error), explanation faithfulness (% of explanations whose cited drivers match actual top SHAP features — target ~100%), and band stability under small perturbations.

## Stack

- **Agent harness:** Deep Agents (`deepagents`) on **LangGraph** (durable execution, checkpointing, streaming, HITL interrupts).
- **Decisioning:** Python — XGBoost/sklearn + SHAP, versioned. Never an LLM.
- **Knowledge brain:** Docling → CocoIndex → GBrain.
- **Integrations:** MCP servers (one per external system), synthetic ↔ sandbox via per-connector config flag.
- **Primary store:** PostgreSQL (profiles, scores, applications; also GBrain search index + CocoIndex state).
- **Observability:** LangSmith + OpenTelemetry.
- **Models:** small model for routing/classification, larger for reconciliation + explanations. Use the latest Claude models (Opus 4.8 / Sonnet 4.6) — verify model IDs via the `claude-api` skill before hardcoding.
- **Deferred (leave clean seams, don't build now):** Temporal (durability at scale), A2A (cross-org federation).

## The golden demo path (`06-build-plan-and-demo.md` — build this first, freeze ~day 18)

Lakshmi (credit-invisible kirana owner) → consent → parallel ingest → live reconciliation (fraud flag on the fraud archetype) → **Health Card renders** (composite + 5 gauges + confidence) → **HITL pause** with full explanation → underwriter approves → Action agent creates OCEN offer + opens LOS application → audit log + portfolio view. The two winning beats: the Health Card appearing for someone the system used to reject, and the agent pausing for a human with a full explanation.

**MVP cut line — build now:** scoring + reconciliation, ingestion on synthetic data, Health Card UI, HITL gate + audit log, offer/action end-to-end. **Only if time remains:** live monitoring agent, multi-language explanations, full portfolio analytics.

## Conventions

- Working state lives in the virtual filesystem as files (`canonical/{app_id}.json`, `features/{app_id}.json`, `recon/{app_id}.md`, `audit/{app_id}.log`), **not** in message history.
- Every external effect goes through an MCP tool (the governance layer logs it automatically).
- Keep each subagent single-purpose — breadth kills reliability.
- All data is synthetic/sandbox during the challenge: no real PII, no real money movement. State this explicitly — it reads as maturity.
- No commands/build/test scripts exist yet — add them here once the project is scaffolded (Python decisioning service, agent harness, UI).

## Open question to settle early

What amount/risk threshold auto-flows to the HITL interrupt vs. surfaces as a fully-automated recommendation. That one parameter shapes the whole demo narrative.
