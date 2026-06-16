# 03 — Agent Specifications

*Per-subagent contracts. CredSight is one **deep agent** (the orchestrator) that delegates to specialist **subagents** via the built-in `task` tool, each in an isolated context window. Subagents reach external systems only through permissioned **MCP tools**, store working data in the **virtual filesystem** (not the prompt), and the credit decision pauses at a **human-in-the-loop interrupt**. Keep each subagent single-purpose — breadth kills reliability.*

---

## Conventions
- **Shared working state** lives in the **virtual filesystem** (pluggable backend = LangGraph store), not in the message history. Subagents read/write files like `canonical/{app_id}.json`, `features/{app_id}.json`, `recon/{app_id}.md`, `audit/{app_id}.log`. This is the "storage" capability in action — context stays small across a long run.
- Each subagent declares: `name`, `description` (when the orchestrator should call it), `tools` (MCP + internal), `system_prompt`, and `permissions` (file + tool scopes).
- Every external effect goes through an MCP tool, which the governance layer logs automatically.
- Long-term facts (MSME profile, prior assessments, override history) persist in the **long-term memory store** across threads.

---

## 1. Orchestrator (top-level deep agent)
- **Role:** plan the application with `write_todos`, delegate to subagents via `task`, own the HITL pause, enforce bounded loops/timeouts.
- **Tools:** `task` (spawn subagents), `write_todos`, filesystem, `knowledge.search`.
- **Inputs:** trigger event (new application / re-score). **Outputs:** terminal state (`approved`/`rejected`/`needs_info`/`pending_human`).
- **Permissions:** coordination only — cannot call action/money tools.
- **Guardrails:** bounded total runtime; every step has a fallback; verifies subagent outputs before advancing.

## 2. Consent & Ingestion subagent
- **Description (when to call):** "pull and normalise an MSME's alternate data with consent."
- **Does:** initiates AA consent (or replays a sandbox consent artefact); fetches bank/GST/UPI/EPFO/bureau **in parallel**; normalises to the canonical schema; **writes `canonical/{app_id}.json` to the filesystem** and returns only a short summary to the orchestrator.
- **MCP tools:** `aa.fetch_statements`, `gst.fetch_returns`, `upi.fetch_txns`, `epfo.fetch`, `bureau.fetch`.
- **Permissions:** read-only on data tools, scoped to the consent artefact; write to `canonical/`.
- **Guardrails:** per-source retry + timeout; **partial success allowed** (missing source → flag + lower confidence, not failure); never proceeds without a valid consent artefact.

## 3. Reconciliation & Enrichment subagent  *(the hard last mile — invest here)*
- **Description:** "cross-validate and enrich the canonical data; flag fraud/inconsistencies."
- **Does:** reconciles turnover/income across GST vs bank vs UPI; resolves disagreements with documented rules; flags gaming/fraud (circular UPI, anomalous pre-application inflows, GST-vs-bank gaps beyond tolerance); tags seasonality; derives features → **writes `features/{app_id}.json` + `recon/{app_id}.md`**.
- **MCP tools:** `knowledge.search` (sector norms / known fraud patterns from GBrain).
- **Permissions:** read `canonical/`, write `features/`,`recon/`; read-only knowledge.
- **Guardrails:** every flag is rule-backed and logged with evidence; LLM reasoning triages/explains rule hits, never invents them.

## 4. Scoring & Decisioning subagent
- **Description:** "compute the health score and a policy-checked credit recommendation."
- **Does:** calls the **deterministic model service** (score + SHAP, not an LLM); checks the candidate decision against credit policy retrieved from the knowledge brain; emits a recommendation + amount/rate/tenor.
- **MCP tools:** `score_model.predict`, `knowledge.search`.
- **Permissions:** read `features/`; call model + knowledge; **cannot** execute loan actions.
- **Guardrails:** always a *recommendation*; the LLM never computes/overrides the score; out-of-policy → forced to human review.

## 5. Explainability subagent
- **Description:** "explain the score and decision for the MSME, the underwriter, and the audit log."
- **Does:** turns SHAP drivers + policy refs into MSME-facing plain-language/vernacular text and a structured underwriter/regulator rationale; attaches the thin-file confidence note → **writes to `audit/{app_id}.log`**.
- **MCP tools:** none external (LLM over provided structured inputs).
- **Guardrails:** **faithfulness check** — generated text may reference only the model's actual top SHAP drivers and retrieved clauses; fails closed to a templated explanation.

## 6. HITL Approval Gate  *(Deep Agents human-in-the-loop interrupt)*
- **Mechanism:** configured as human approval on the money-moving tool. When `amount > threshold` OR `recommendation == reject` OR `confidence < floor` OR `out_of_policy`, the run **interrupts**; the underwriter console shows the recommendation + explanation + evidence; the human approves / overrides / requests info; the run **resumes**.
- **Captured:** human identity + reason, immutably. Overrides feed back into the eval set.
- **Guardrails:** no downstream action runs until this clears.

## 7. Offer & Action subagent  *(runs only post-approval)*
- **Description:** "execute the approved offer in the bank's systems."
- **Does:** generates the OCEN/ULI offer, creates/updates the loan application in the LOS, requests missing docs, books the outcome.
- **MCP tools:** `ocen.create_offer`, `los.create_application`, `los.request_docs`, `notify.msme`.
- **Permissions:** the **only** subagent allowed action tools, and only when `status == approved`.
- **Guardrails:** idempotency key per application (no double-booking); every action logged; rollback path for partial failures.

## 8. Monitoring & Early-Warning subagent  *(async, long-running)*
- **Description:** "watch onboarded MSMEs for emerging stress and re-score."
- **Does:** runs as an **async subagent** on a schedule; re-ingests fresh AA/GST/UPI signals, re-scores, flags stress; raises alerts via the orchestrator.
- **MCP tools:** ingestion tools (read-only) + `score_model.predict`.
- **Guardrails:** read-only; alerts are recommendations to a human, never automated actions on live loans.

---

## Subagent config — worked example (deepagents)
```python
scoring = {
    "name": "scoring_decisioning",
    "description": "Compute the MSME multidimensional health score and a "
                   "policy-checked credit recommendation. Call after features are ready.",
    "system_prompt": SCORING_PROMPT,          # 'never compute the score yourself; call the tool'
    "tools": ["score_model.predict", "knowledge.search"],
    # least-privilege: read features/, no action tools, no money movement
}

# the orchestrator spawns this via the built-in `task` tool; isolated context window
```

## A note on storage (the capability to showcase)
Three storage tiers, all native to the harness:
1. **Virtual filesystem (per-run working memory):** canonical data, features, reconciliation notes, draft explanations, audit log — keeps the prompt small and gives the demo a visible "agent scratchpad."
2. **Long-term memory store (across runs):** MSME profiles, prior assessments, underwriter override history — so re-applications and monitoring build on history.
3. **Knowledge brain (GBrain):** shared, self-organising domain knowledge the agents read *and write* (policy, sector norms, learned fraud patterns).

## Implementation order (so the demo path comes up first)
1. Scoring & Decisioning + the model service (the core).
2. Consent & Ingestion (real-ish data flowing in, written to the filesystem).
3. Reconciliation & Enrichment (the moat — deepen as time allows).
4. Explainability (makes the Health Card sing).
5. HITL interrupt + audit log (the trust centrepiece of the demo).
6. Offer & Action (closes the loop on stage).
7. Monitoring async subagent (if time remains — strong for the "portfolio quality" slide).
