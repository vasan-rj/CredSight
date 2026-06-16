# 01 — The Idea, Reframed as an Agentic OS

*Output of the agentic-startup-advisor lens (SHAPE mode). This is the conceptual contract: every architectural and product decision in the other docs exists to serve what's here.*

---

## The idea in one line
An agent that takes a credit-invisible MSME from "unknown to the bank" to "assessed, offered, onboarded, and monitored" — using alternate data, with a human approving the real money decisions and a full audit trail behind every step.

## Where the naive version sits on the lens (and why that loses)
The obvious build — "ingest alternate data, compute a score, render a Health Card" — is **assistant-shaped, not OS-shaped**. It ingests and decides, but it stops at *suggesting* a number to a human. Under the 2026 thesis that's a vitamin: a dashboard. Dashboards are features, and features get absorbed by whoever owns the workflow (here, the bank's loan-origination system). It's also exactly what most hackathon teams will build, so it doesn't differentiate.

The fix is to **close the loop and own the workflow.**

## The agentic loop CredSight must close

| Stage | What a wrapper does | What CredSight does |
|-------|--------------------|--------------------|
| **Ingest** | User pastes/uploads a file | Orchestrates AA consent, pulls bank statements + GST returns + UPI/QR flows + EPFO, normalises messy multi-source data |
| **Decide** | LLM "estimates" a score | Deterministic, versioned ML model computes a multidimensional health score + an eligibility decision, grounded in the bank's actual credit policy |
| **Act** | Shows a number | Generates an OCEN/ULI-style offer, opens the loan application in the LOS, requests missing docs from the MSME, books the decision — real actions in real systems |
| **Log / govern** | Nothing | Immutable audit of every action, source, model version, and rationale; scoped permissions; **human approval gate** on real decisions; runs in a sandbox |

Text/score-out is level 0. Ingest + decide but only suggests = assistant. **All four = the operating system.** CredSight is built to be all four.

## The seven lens questions, answered

1. **Wrapper or operating system?** OS — only if it acts and logs. The Health Card alone is the wrapper trap; the agent that runs the workflow around it is the OS. *This is the single most important cut, and it's the whole pivot.*
2. **Owns a workflow or a feature?** Owns the **credit-invisible-MSME onboarding & underwriting workflow** end to end — not just the scoring step. Scoring is one node in a graph it owns.
3. **Deep, painful, recurring niche?** Yes. NTC/NTB MSME underwriting is unglamorous, high-frequency, and high-pain for banks (high rejection, missed viable borrowers, slow inclusion). Depth lives in alternate-data reconciliation — the part a generalist can't fake.
4. **B2B?** Yes — sold to the bank; the bank serves the MSMEs. Budgets, measurable ROI (approval rate ↑, portfolio quality held), recurring workflow.
5. **Guardrails designed in?** This is a money-movement vertical, so guardrails *are the product*: HITL approval on decisions over a threshold (and on every auto-reject), scoped least-privilege tool access, immutable audit, explainability + a thin-file confidence flag, and a sandbox. This is also the exact thing that earns trust from a risk-averse bank — sell it as a feature, loudly.
6. **Where's the hard last mile?** The ugly 20%: thin/sparse files, turnover that disagrees across GST vs bank vs UPI, seasonal businesses, fraud/gaming of alternate signals, and producing a rationale a regulator will accept. Solve this and you have a moat. Hand-wave it and you have demo-ware.
7. **Capital / pull zone?** Warm. India's public credit rails (ULI, OCEN, Account Aggregator/Sahamati) are being actively pushed by RBI and adopted by banks — the buyer is ready and the narrative is in season.

## The wedge (where to start narrow)
Don't try to underwrite every loan type on day one. **Beachhead: working-capital / unsecured small-ticket credit for NTC/NTB micro-enterprises** (kirana, small services, micro-manufacturing) where traditional documents are weakest and alternate data is richest. It's the highest-pain, highest-rejection segment — the place the agentic approach most obviously beats the status quo. Expand to secured/larger products once the workflow is trusted.

## The moat, stated plainly
Not the model (commoditising) and not "better prompts." The moat is: **(a)** owning the end-to-end workflow inside the bank's systems, **(b)** the reconciliation/fraud logic that makes alternate data trustworthy (the hard last mile), and **(c)** the trust layer (audit + explainability + HITL) that took real work to make a regulator comfortable. Rip out the LLM and there's still a workflow engine, a data-reconciliation asset, and a governance system left standing — that's the test a wrapper fails.

## Commoditisation check
When the next model is 2× better and 10× cheaper: **tailwind, not extinction.** Cheaper/stronger models make the reconciliation and explanation steps better and cheaper, but the value sits in the owned workflow, the integrations, the proprietary reconciliation logic, and the trust layer — none of which a model release replaces. (Contrast a "GST-statement-summariser chatbot," which a better model erases.)

## The single biggest risk + the cheap de-risking move
**Risk:** trust in an autonomous credit decision — a bank will not let software move money on a black-box call, and a wrong auto-approval is catastrophic.
**De-risk it for ~₹0:** make the **HITL approval gate and the explainability/audit trail the centrepiece of the demo**, not an afterthought. Show the agent doing the work, then pausing at the decision and handing a fully-explained recommendation (with the thin-file confidence flag) to a human underwriter who approves/overrides — every action logged. That single design choice converts "scary autonomous lender" into "tireless analyst that a human signs off on," which is exactly what a bank can buy and a judge can trust.

## Next concrete move
Lock the workflow state machine on paper (the nodes in `02-architecture.md`) and build the deterministic scoring service + reconciliation logic on synthetic data **first** — that's the substance and the hard last mile. The agentic shell and the Health Card UI wrap around a core that already works.
