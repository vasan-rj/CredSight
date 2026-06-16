# 05 — Data & Integrations

*How data gets in and how actions go out. The whole integration layer is designed so "synthetic now → IDBI sandbox later" is a config swap, not a rewrite.*

---

## The adapter principle
Every external system sits behind a **clean connector interface** exposed as an **MCP tool server**. Each connector has two implementations:
- `SyntheticAdapter` — serves generated data / simulates the flow (used during the challenge).
- `SandboxAdapter` — calls IDBI's sandbox APIs (wired in the day you're shortlisted).
Agents call the MCP tool; they never know or care which adapter is behind it. This is what makes the "deployment-ready" claim true rather than a slide.

```
Agent ──(MCP call)──> Connector Interface ──> { SyntheticAdapter | SandboxAdapter } ──> source
```

## Data sources & what they give you

| Source | Access path (real) | Signals used | Synthetic strategy |
|---|---|---|---|
| **Bank statements** | Account Aggregator (Sahamati framework) | balances, inflows/outflows, bounces, obligations | Generate per-archetype statements (regular/seasonal/stressed) |
| **GST returns** | GSTN / sandbox | turnover trend, filing punctuality, input-output | Generate GSTR-style monthly summaries tied to the same archetype |
| **UPI / QR** | UPI txn history (via AA / bank) | txn count/value, payers, seasonality, fraud flags | Generate merchant-style UPI flows consistent with the bank data |
| **EPFO** | EPFO sandbox | employee count, contribution continuity | Optional; generate for "has employees" archetypes |
| **Bureau** | CIBIL/Experian sandbox | existing obligations, DPD | Present for NTB-with-history; absent for true NTC |
| **Credit policy docs** | Bank-provided PDFs | eligibility/scheme rules for the knowledge brain | Parse with Docling; use public scheme docs as stand-ins |

> Keep the data **internally consistent per MSME archetype** — the same shop's GST turnover, bank inflows, and UPI volume should roughly agree (the Reconciliation agent's tolerance checks depend on it, and inconsistent synthetic data makes the demo look broken).

## The agentic knowledge brain (Docling → CocoIndex → GBrain)
The bank's policy/scheme knowledge isn't a static vector store — it's a brain the agents read *and write* to.

```
Policy & scheme PDFs ──Docling──> clean Markdown/JSON (tables, layout, page+bbox metadata)
                                        │
                                   CocoIndex (incremental: chunk → embed → upsert)
                                        │            └─ reprocesses only changed docs
                          ┌─────────────┴─────────────┐
                     vector store                knowledge graph
                          └─────────────┬─────────────┘
                                      GBrain
            (Markdown = source of truth · Postgres/PGLite = search index · MCP = agent access)
              capture (write learnings) · search (retrieve at decision time) · organize (nightly)
```

- **Docling (IBM, MIT):** parses messy policy PDFs/DOCX into structured Markdown/JSON, preserving tables and layout, with page/bounding-box metadata so a retrieved clause can be cited precisely in the audit trail.
- **CocoIndex (Apache-2.0):** the incremental indexing pipeline — chunk, embed, and upsert into both a vector store and a knowledge graph; only changed documents are reprocessed, so policy updates stay fresh without a full re-index. (Postgres holds its pipeline state.)
- **GBrain (MIT):** the agentic knowledge base — Markdown is the operator-owned source of truth, a hybrid Postgres index makes it searchable, and MCP exposes it to the agents. Agents **search** policy/sector norms at decision time and **capture** new derived knowledge (e.g., a newly observed fraud pattern) back into the brain; a nightly **organize** cycle keeps the graph self-wiring. Exposed to agents via the `knowledge.search` / `knowledge.capture` MCP tools.

> Why this beats plain RAG for a bank: precise, citable grounding (Docling metadata), always-fresh policy (CocoIndex incrementality), and a knowledge base that *improves with use* because the agents write learnings back (GBrain) — defensible, auditable, and a genuine differentiator in the pitch.

## Outbound (action) integrations

| Target | MCP tool | Action |
|---|---|---|
| **OCEN / ULI** | `ocen.create_offer` | Generate a standards-shaped credit offer |
| **LOS (Loan Origination System)** | `los.create_application`, `los.request_docs` | Open/advance the application; request missing docs |
| **Notification** | `notify.msme` | Tell the MSME their status / what to upload |

## MCP tool contracts (sketch — make these typed)
```jsonc
// Ingestion (read-only, consent-scoped)
"aa.fetch_statements":  { in: { msme_id, consent_id, from, to }, out: { accounts[], txns[] } }
"gst.fetch_returns":    { in: { gstin, periods[] },             out: { returns[] } }
"upi.fetch_txns":       { in: { vpa|msme_id, from, to },        out: { txns[] } }
"epfo.fetch":           { in: { establishment_id },             out: { employees, contributions[] } }

// Decisioning
"score_model.predict":  { in: { features },                     out: { dimensions{}, composite, shap[], confidence } }
"knowledge.search":     { in: { query, segment },               out: { clauses[], sources[] } }  // GBrain-backed
"knowledge.capture":    { in: { note, tags[] },                 out: { ok } }                    // agents write learnings back

// Action (write — permissioned, post-approval, idempotent)
"ocen.create_offer":    { in: { application_id, amount, rate, tenor }, out: { offer_id } }
"los.create_application":{ in: { msme_profile, decision, idempotency_key }, out: { application_ref } }
"los.request_docs":     { in: { application_ref, doc_list[] },  out: { ok } }
```

## Synthetic data plan (build this in the first 2 days)
- Define **3 base archetypes**: *thin-file micro* (UPI + partial GST only), *strong* (consistent GST/bank/UPI growth), *stressed* (declining turnover, bounces, rising obligations). Plus a *fraud* variant (circular UPI, pre-application inflow spike) to demo the reconciliation flag.
- Generate a coherent bundle per synthetic MSME so all sources agree (or disagree *intentionally* for the fraud case).
- Seed ~20–50 MSMEs so the lender/portfolio view looks real.
- Store generators in the repo so data is reproducible and reviewable — and so swapping to sandbox data doesn't touch agent code.

## Consent, privacy & compliance (say this out loud in the pitch)
- **Consent-first:** ingestion only runs against a valid Account Aggregator consent artefact; the consent scope is enforced at the MCP tool boundary (an agent can't read beyond what was consented).
- **DPDP-aware:** treat all pulled data as personal/financial data — minimise, scope, and log access; don't retain beyond purpose.
- **Auditable consent:** the consent artefact reference is written into the immutable audit log alongside every data pull, so "what did we access, with whose permission, when" is always answerable.
- For the challenge everything is synthetic/sandbox — **no real PII, no real money movement** — and you should state that explicitly to judges; it reads as maturity, not a limitation.

## Sandbox-readiness checklist (what makes the deployment claim credible)
- [ ] Connector interfaces defined; `SyntheticAdapter` complete; `SandboxAdapter` stubbed with the real API shapes.
- [ ] MCP tool contracts typed and versioned.
- [ ] Consent artefact modelled and enforced at the tool boundary.
- [ ] Idempotency keys on all write actions.
- [ ] Config flag flips synthetic ↔ sandbox per connector (no code change in agents).
