# CredSight — Product Requirements Document

> **CredSight** — an agentic credit-underwriting operating system that turns credit-invisible MSMEs into bankable borrowers.
> Built for **IDBI Innovate 2026 — Track 03 (Financial Inclusion / Digital Lending / Credit Decisioning)**.
> Status: PRD v1 · synthetic-data build · sandbox-ready by design.

---

## 1. Summary

CredSight runs the full credit-invisible-MSME underwriting workflow — **ingest → decide → act → log** — as a single deep agent that takes real actions in the bank's tools, pauses for a human at the credit decision, and leaves an immutable audit trail. The human-facing surface is the **MSME Financial Health Card**; the substance underneath is a deterministic, explainable scoring core wrapped in an agentic harness with governance built in.

**North star:** not a scoring dashboard — an agent that *owns* the underwriting workflow end to end, with a human-in-the-loop approval gate that makes autonomy safe for a bank to buy.

## 2. Problem

- India has ~63M MSMEs; most are **credit-invisible** (New-To-Credit / New-To-Bank) and lack the formal financial documents traditional underwriting requires.
- Result for the bank: high rejection rates, missed viable borrowers, slow financial inclusion, and manual underwriting that doesn't scale.
- Alternate data (GST, UPI, Account Aggregator bank flows, EPFO) exists but is messy, multi-source, conflicting, and gameable — making it hard to underwrite on safely and defensibly.
- A bank cannot deploy a black-box automated credit decision: it needs reproducibility, explainability, consent compliance, and a human accountable for money-movement.

## 3. Goals & non-goals

### Goals
- Aggregate alternate data (GST, UPI, AA, EPFO, optional bureau) under consent.
- Compute a **multidimensional, deterministic, explainable** financial-health score with an honest thin-file confidence indicator.
- Run the end-to-end workflow: consent → ingest → reconcile → score → explain → **human approval** → offer/action in LOS/OCEN → monitor.
- Make every step auditable: data source + consent ref, model version + inputs/outputs, every tool action, every human decision.
- Be **deployment-ready**: synthetic data today, IDBI sandbox APIs via a config swap.

### Non-goals (challenge scope)
- No real money movement, no real PII — synthetic/sandbox only.
- No underwriting of every loan product on day one (beachhead below).
- No LLM-computed credit scores or decisions — ever.
- Temporal (durability at scale) and A2A (cross-org federation) are deferred; leave clean seams.

## 4. Target users & beachhead

- **Buyer:** the bank (IDBI). **End-served:** the MSME.
- **Beachhead segment:** working-capital / unsecured small-ticket credit for NTC/NTB micro-enterprises (kirana, small services, micro-manufacturing) — highest-pain, highest-rejection, richest in alternate data. Expand to secured/larger products once trusted.

### Personas
- **MSME owner (e.g. Lakshmi, kirana):** wants credit, has no audited financials; interacts with the Health Card + consent flow.
- **Underwriter / credit officer:** reviews the agent's recommendation at the HITL gate; approves / overrides / requests info.
- **Risk & compliance team / regulator:** consumes the audit trail, explainability, and confidence indicators.

## 5. Product principles (binding)

1. **The score is deterministic and auditable; the LLM never does the credit math.** A versioned ML model (XGBoost + SHAP) decides; LLMs orchestrate, reconcile, and explain.
2. **Guardrails are the product, not overhead.** HITL approval, scoped permissions, immutable audit, explainability, sandboxing — these are what make it buyable.
3. **Own the workflow, not a step.** Scoring is one node in a graph CredSight owns.
4. **The hard last mile is the moat.** Thin files, conflicting cross-source turnover, fraud/gaming, regulatory explainability — solve the ugly 20%.
5. **Sandbox-ready by design.** Connectors are swappable interfaces: `SyntheticAdapter` now, `SandboxAdapter` on shortlist — a config change, not a rewrite.
6. **Build the deterministic core first**, then wrap it in the agentic harness.

## 6. Functional requirements

### 6.1 Consent & ingestion
- FR-1: Initiate (or replay a sandbox) Account Aggregator consent artefact before any data pull.
- FR-2: Fetch bank / GST / UPI / EPFO / bureau **in parallel**; normalise to a canonical schema; write `canonical/{app_id}.json` to the virtual filesystem.
- FR-3: Enforce consent scope at the MCP tool boundary — an agent cannot read beyond what was consented.
- FR-4: Partial success allowed — a missing source lowers confidence and raises a flag; it does not fail the run.

### 6.2 Reconciliation & enrichment (the moat)
- FR-5: Cross-check turnover/income across GST vs bank vs UPI; compute agreement ratios; resolve disagreements with documented, logged rules.
- FR-6: Flag fraud/gaming with rule-backed evidence (circular UPI, anomalous pre-application inflow spikes, GST-vs-bank gaps beyond tolerance).
- FR-7: Tag seasonality; derive model features → `features/{app_id}.json` + `recon/{app_id}.md`.
- FR-8: LLM reasoning triages/explains rule hits; it never invents flags.

### 6.3 Scoring & decisioning
- FR-9: Compute five dimension sub-scores (0–100) and a composite scaled to a **300–900** band via a deterministic, versioned model.
- FR-10: Emit SHAP attributions (top positive/negative drivers) per applicant.
- FR-11: Produce a thin-file **confidence ∈ [0,1]** from #sources present, months of history, and cross-source agreement.
- FR-12: Map composite band → eligible product / amount range / indicative rate band / tenor, **checked against credit-policy clauses** retrieved from the knowledge brain before becoming a recommendation.
- FR-13: Always output a *recommendation*; out-of-policy forces human review.

### 6.4 Explainability
- FR-14: Render MSME-facing plain-language (and optionally vernacular) explanations and a structured underwriter/regulator rationale → `audit/{app_id}.log`.
- FR-15: **Faithfulness check** — generated text may reference only the model's actual top SHAP drivers and retrieved clauses; fails closed to a templated explanation.

### 6.5 HITL approval gate
- FR-16: Interrupt the run for human approval when `amount > threshold` OR `recommendation == reject` OR `confidence < floor` OR `out_of_policy`.
- FR-17: Surface recommendation + explanation + evidence to the underwriter console; capture human identity + reason immutably; resume on decision.
- FR-18: No downstream action runs until the gate clears. Overrides feed the eval set.

### 6.6 Offer & action (post-approval only)
- FR-19: Generate an OCEN/ULI-shaped offer; create/advance the loan application in the LOS; request missing docs; notify the MSME.
- FR-20: Idempotency key per application (no double-booking); every action logged; rollback path for partial failures.
- FR-21: This is the **only** component with write/action permissions, and only when `status == approved`.

### 6.7 Monitoring & early-warning (async, optional)
- FR-22: Periodically re-ingest fresh AA/GST/UPI signals and re-score onboarded MSMEs to flag emerging stress.
- FR-23: Read-only — alerts are recommendations to a human, never automated actions on live loans.

### 6.8 Governance & audit (cross-cutting)
- FR-24: Append-only immutable audit log of every state transition, data pull (with consent-artefact ref), model version + I/O, tool action, and human decision.
- FR-25: Least-privilege permissions per subagent (file + tool scopes); ingestion read-only, only action subagent can move money.

## 7. The Financial Health Score

Five interpretable dimensions, each 0–100, weighted into a composite scaled to **300–900**:

| Dimension | Weight | Captures | Sources |
|---|---|---|---|
| Cash-flow health | 30% | inflow regularity, avg balance, volatility, inflow/outflow ratio, seasonality | Bank (AA), UPI/QR |
| GST & turnover signal | 20% | turnover trend, filing punctuality/continuity, input-tax behaviour | GST |
| Banking discipline | 20% | bounces, returns, overdraft behaviour, obligation servicing | Bank (AA) |
| Business vintage & stability | 15% | GST registration age, filing continuity, operational/address stability | GST, profile |
| Obligation load / formality | 15% | existing EMI load vs inflow, leverage; EPFO as scale/formality proxy | AA, EPFO, bureau |

- **Per-dimension sub-scores:** transparent monotonic transforms / lightweight models (independently explainable).
- **Composite:** calibrated XGBoost (isotonic/Platt) for ranking; expose the weighted-dimension view for interpretability. Show both.
- **Weights are config** — calibrate against synthetic outcome labels; document any change (auditability).
- **Confidence** travels with every score and routes low-confidence cases to the HITL gate.

## 8. Architecture

A single **deep agent orchestrator** (Deep Agents `create_deep_agent` on the LangGraph runtime) plans with `write_todos` and delegates to single-purpose **subagents** via the `task` tool, each in an isolated context window. External systems are reached only through permissioned **MCP tool servers**. Working state lives in a **virtual filesystem** (backend = LangGraph store), not the prompt. The credit decision pauses at a **HITL interrupt**.

### Subagents
Orchestrator · Consent & Ingestion · Reconciliation & Enrichment · Scoring & Decisioning · Explainability · HITL Approval Gate · Offer & Action · Monitoring & Early-Warning. (Full contracts: `reference-docs/03-agent-specs.md`.)

### Three storage tiers
- **Virtual filesystem** (per-run working memory): `canonical/`, `features/`, `recon/`, `audit/`.
- **Long-term memory store** (cross-run): MSME profiles, prior assessments, override history.
- **Knowledge brain (GBrain)** (shared, self-organising): policy clauses, sector norms, learned fraud patterns — agents read **and write**.

### Knowledge brain
**Docling** (parse policy PDFs → structured Markdown/JSON with page/bbox metadata) → **CocoIndex** (incremental chunk/embed/upsert into vector store + KG) → **GBrain** (Markdown source of truth, Postgres/PGLite hybrid search, MCP access). Tools: `knowledge.search`, `knowledge.capture`. Every retrieved clause is cited in the audit rationale.

## 9. Data & integrations

Every external system sits behind a clean connector interface exposed as an MCP tool, with two implementations: `SyntheticAdapter` (now) and `SandboxAdapter` (IDBI sandbox, on shortlist). Agents call the MCP tool and never know which adapter is behind it.

### MCP tool contracts (typed)
- **Ingestion (read-only, consent-scoped):** `aa.fetch_statements`, `gst.fetch_returns`, `upi.fetch_txns`, `epfo.fetch`, `bureau.fetch`
- **Decisioning:** `score_model.predict`, `knowledge.search`, `knowledge.capture`
- **Action (write, permissioned, post-approval, idempotent):** `ocen.create_offer`, `los.create_application`, `los.request_docs`, `notify.msme`

### Synthetic data
Three base archetypes + a fraud variant, **internally consistent per MSME** (same shop's GST turnover, bank inflows, UPI volume roughly agree):
- **thin-file micro** (UPI + partial GST only)
- **strong** (consistent GST/bank/UPI growth)
- **stressed** (declining turnover, bounces, rising obligations)
- **fraud** (circular UPI, pre-application inflow spike — demos the reconciliation flag)

Seed ~20–50 MSMEs for a realistic portfolio view. Generators live in the repo (reproducible, reviewable; swapping to sandbox data touches no agent code).

## 10. Consent, privacy & compliance

- **Consent-first:** ingestion only runs against a valid AA consent artefact; scope enforced at the MCP tool boundary.
- **DPDP-aware:** treat all pulled data as personal/financial — minimise, scope, log access, don't retain beyond purpose.
- **Auditable consent:** the consent-artefact reference is written into the immutable audit log alongside every data pull.
- Challenge build is fully synthetic/sandbox — no real PII, no real money movement.

## 11. Non-functional requirements

- **Accuracy & explainability** (priority #1): every decision reproducible and defensible to a risk team/regulator.
- **Reliability & auditability:** LangGraph checkpoints at each node — a crash mid-assessment resumes, not restarts; bounded subagent loops (max iterations + wall-clock timeout); idempotent action tools.
- **Fault tolerance:** per-source retries + timeouts; defined partial-success path (GST down → proceed flagged, lower confidence); LLM fallbacks (smaller model / cached template) so explanation never blocks a decision.
- **Scalability:** stateless subagents (state in LangGraph store + Postgres); parallel ingestion fan-out; async monitor off the request path; CocoIndex incremental index (no full re-embed).
- **Latency:** near-real-time via parallel ingestion, context offload to files, right-sized models — never at the cost of accuracy.
- **Observability:** LangSmith + OpenTelemetry tracing the agent graph; eval loop in CI.

## 12. Evaluation harness (CI from day one)

- **Decision quality:** AUC/KS ranking + calibration error against synthetic ground-truth labels (good/stressed/default archetypes).
- **Explanation faithfulness:** % of explanations whose cited drivers match the model's actual top SHAP features — target ~100%.
- **Stability:** small input perturbations must not swing the band.
- Three fixed regression archetypes (thin-file, strong, stressed) re-run on every change.

## 13. Success metrics

- **Business (bank-facing):** approval rate of credit-invisible MSMEs ↑ while portfolio quality held; time-to-decision (near-real-time vs days); % decisions human-approved + fully audited (target 100%).
- **Model:** ranking (AUC/KS), calibration error, explanation faithfulness ~100%, band stability.
- **Demo/selection:** golden path runs end-to-end; HITL pause + audit trail land as the trust story.

## 14. Build plan (24 days, integration freeze ~day 18)

| Days | Focus |
|---|---|
| 1–2 | Lock workflow state machine; design dimensions/weights; build synthetic data generators (3 archetypes + fraud); golden path; roles |
| 3–6 | Scoring service + SHAP + reconciliation logic on synthetic data; eval harness with 3 regression archetypes — **the core works & is explainable** |
| 7–10 | Ingestion agent + canonical schema; Health Card UI (hero screen); consent flow simulation |
| 11–14 | HITL approval gate + immutable audit log; Explainability agent (plain-language + faithfulness check) — **the trust layer** |
| 15–17 | Offer & Action agent (OCEN/LOS stubs); orchestrator + subagents on Deep Agents + LangGraph; underwriter console |
| 18 | **Integration freeze** — whole golden path runs end-to-end |
| 19–21 | Polish Health Card + audit UI; record demo video; build deck |
| 22–24 | Rehearse ×2; deployability note; **submit early** |

### MVP cut line
- **Build now:** scoring + reconciliation, ingestion on synthetic data, Health Card UI, HITL gate + audit log, offer/action end-to-end.
- **Only if time remains:** live monitoring agent, multi-language explanations, full portfolio analytics, edge-archetype polish.

## 15. Golden demo path

Lakshmi (credit-invisible kirana owner) → consent → parallel ingest → live reconciliation (fraud flag on fraud archetype) → **Health Card renders** (composite + 5 gauges + confidence) → **HITL pause** with full explanation (SHAP + policy refs + confidence) → underwriter approves → Action agent creates OCEN offer + opens LOS application → audit log + portfolio view. The two winning beats: the Health Card appearing for someone the system used to reject, and the agent pausing for a human with a full explanation.

## 16. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Bank won't trust autonomous credit decision | HITL gate + explainability + immutable audit as the demo centrepiece; agent recommends, human signs off |
| Alternate data is gameable | Rule-backed fraud flags + cross-source reconciliation; confidence flag on thin files |
| Bias in alternate data | Monitor for it, surface confidence, keep a human in the loop |
| "Is it accurate enough to lend on?" | Explainable + calibrated ranking on synthetic archetypes; back-test on sandbox data; every decision human-approved + logged → safe to pilot before perfect |
| Sandbox access timing | Synthetic-behind-adapters now; swap is a config change |

## 17. Open questions

- What amount/risk threshold auto-flows to the HITL interrupt vs. surfaces as a fully-automated recommendation? (Shapes the demo narrative — settle first.)
- Verify official IDBI Innovate 2026 submission checklist + deadline against the real event page (the 24-day plan is a planning assumption).
- Which dimension weights survive calibration against synthetic labels.

---

*Source of truth for detail: `reference-docs/01`–`07`. This PRD consolidates them into a single requirements view; on any conflict, the reference pack governs and this doc is updated.*
