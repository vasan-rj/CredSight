# 06 — Build Plan & Demo

*Sequencing the 24 days and the pitch, tuned to win selection. The rule that overrides everything: build the golden demo path first, freeze new features at ~day 18, and protect the last stretch for the deck, demo video, and rehearsal.*

---

## The golden demo path (only this must be truly real on stage)
1. Open on **Lakshmi**, a pre-seeded credit-invisible kirana owner — no audited financials, no prior loan.
2. "Connect data with consent" → simulated **Account Aggregator** consent → the **Ingestion agent** pulls bank/GST/UPI/EPFO (show the parallel fetch).
3. The **Reconciliation agent** cross-checks sources live — and on the fraud archetype, visibly flags an anomaly (this is a memorable beat).
4. ★ **The Health Card renders** — composite score (e.g., 718/900), five dimension gauges, top strengths/risks in plain language, **and a confidence indicator**. *This is the magic moment.*
5. The agent reaches the decision and **pauses at the HITL gate**, handing the underwriter a fully-explained recommendation (SHAP drivers + policy refs + confidence).
6. The **underwriter approves** → the **Action agent** generates the OCEN/ULI offer and opens the loan application → "Lakshmi is bankable, decisioned in real time, every step logged."
7. Cut to the **audit log** + **portfolio view**: every action traceable; credit-invisible MSMEs onboarded without dropping portfolio quality.

**The two beats that win it:** the Health Card appearing for someone the system used to reject (#4), and the agent *pausing for a human with a full explanation* (#5) — that's the trust story a bank buys.

## Fake or cut without guilt (none of it is on screen during the magic moment)
Live AA/GST/UPI/EPFO integrations (synthetic behind adapters), live ULI/OCEN connectivity (contract stub), full auth/onboarding, multi-language beyond one demo example, admin screens, the monitoring agent if time is tight (keep one static "early-warning" screenshot for the portfolio slide).

## MVP cut line
**Below the line — build now:** scoring service + reconciliation, ingestion on synthetic data, the Health Card UI, the HITL gate + audit log, the offer/action step end-to-end.
**Above the line — only if time remains:** the live monitoring agent, vernacular explanations beyond one language, the full portfolio analytics, polish on edge archetypes.

## 24-day plan (integration freeze ~day 18)
| Days | Focus | Output |
|---|---|---|
| 1–2 | Lock workflow state machine; design score dimensions/weights; define golden path; **build synthetic data generators** (3 archetypes + fraud); roles | Repo, data, agreed scope |
| 3–6 | **Scoring service + SHAP + reconciliation logic** on synthetic data; eval harness with the 3 regression archetypes | The core works & is explainable |
| 7–10 | Ingestion agent + canonical schema; **Health Card UI** (the hero screen); consent flow simulation | Data → score → card, end to end |
| 11–14 | HITL approval gate (Deep Agents interrupt) + **immutable audit log**; Explainability agent (plain-language + faithfulness check) | The trust layer — your differentiator |
| 15–17 | Offer & Action agent (OCEN/LOS stubs); orchestrator + subagents on Deep Agents + LangGraph; underwriter console | Loop closed: ingest→decide→act→log |
| 18 | **Integration freeze.** Whole golden path runs end-to-end; remove anything off-path | A demoable system |
| 19–21 | Polish the Health Card + audit UI; **record the demo video** of the golden path; build the deck | Backup video + deck |
| 22–24 | Rehearse to time (×2); write the architecture/deployability note; **submit early** with buffer | Submitted, rehearsed |

## Role split (team of up to 4)
- **Lead / pitcher + orchestration:** the deep-agent orchestrator + subagents (Deep Agents + LangGraph), the deck, the clock, and the pitch.
- **ML / decisioning:** scoring service, SHAP, reconciliation logic, eval harness (the moat).
- **Full-stack / demo owner:** Health Card UI, underwriter console, audit view (what judges see — make it beautiful).
- **Integrations / data:** synthetic data generators, MCP connectors + adapters, OCEN/LOS/AA stubs.
(If 3 people: lead absorbs integrations; if 2: cut the monitoring agent and one archetype.)

## Selection deck (~8 slides — quote the bank's own outcome language)
1. **Hook:** "63M MSMEs. Most are credit-invisible. We make them bankable in real time — with a human still in control."
2. **Problem:** NTC/NTB MSMEs lack formal documents → high rejection, missed viable borrowers, slow inclusion (mirror the brief).
3. **Solution:** CredSight — an *agentic* underwriting OS; the Health Card is its surface. Show the four-part loop.
4. **Demo (video):** Lakshmi → card → HITL approval → offer. 60% of the pitch.
5. **How it works:** alternate-data ingestion (AA/GST/UPI/EPFO) → explainable scoring → ULI/OCEN/AA action → audit. One architecture diagram.
6. **Why it's deployable in IDBI:** sandbox-ready connectors, deterministic + explainable decisions, **human-in-the-loop + immutable audit** (the risk-team's fears, pre-answered). Map each point to the bank's expected-outcome clauses.
7. **Impact:** credit-invisible onboarded *without* dropping portfolio quality (show the early-warning/monitoring angle); quantify the addressable NTC/NTB base.
8. **Team & ask:** who you are, why you can build it, request sandbox access + mentorship; memorable closer.

## Why this wins (the contrast to lean on)
Most teams will demo a **static scoring dashboard**. You demo an **agent that runs the workflow, takes the action, and pauses for a human with a full explanation and an audit trail**. For a bank, that difference is the entire ballgame — it's the difference between a nice analytics widget and something they can actually pilot in their sandbox.

## Q&A you must have ready
- **"Is this accurate enough to lend on?"** → explainable, calibrated ranking on synthetic archetypes; we'd back-test on your sandbox data; and every decision is human-approved and logged, so it's safe to pilot before it's perfect.
- **"How is this different from a credit-scoring model?"** → a model is one node; we own the whole workflow — consent-based ingestion, reconciliation, decision, action in your LOS/OCEN, and monitoring — with a trust layer around it.
- **"What's real vs mocked?"** → scoring + reconciliation + the agent loop are real on synthetic data; external integrations are adapter-mocked and swap to your sandbox APIs via config. (Honest, and it shows deployment-readiness.)
- **"Regulatory / privacy?"** → consent-first via AA, DPDP-aware data handling, immutable audit of access + decisions, human approval on real actions.
- **"Bias in alternate data?"** → we monitor for it, surface a confidence flag for thin files, and keep a human in the loop precisely because alternate data can mislead.

## Pre-submission checklist
- [ ] Backup demo video recorded (golden path, ~60–90s, captioned).
- [ ] Deck exported (PDF), architecture diagram legible.
- [ ] Repo clean with a README mapping to the bank's expected outcomes.
- [ ] Deployability note (sandbox-readiness checklist from doc 05).
- [ ] Submitted early; required fields/tags/category confirmed against the official IDBI page.
