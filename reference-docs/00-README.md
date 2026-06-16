# CredSight — Implementation Reference Pack

**CredSight** — an *agentic credit-underwriting operating system* that turns credit-invisible MSMEs into bankable borrowers. The human-facing surface is the **MSME Financial Health Card**; underneath it is an agent that runs the full onboarding → assessment → decision → monitoring workflow, takes real actions in the bank's tools, and logs every step for the risk team and the regulator.

> Built for **IDBI Innovate 2026 — Track 03 (Financial Inclusion / Digital Lending / Credit Decisioning)**.
> Target outcome (from the bank's own brief): aggregate alternate data (GST, UPI, AA, EPFO), compute a multidimensional financial-health score, visualise strengths/risks, integrate with ULI/OCEN/AA, enable near-real-time credit assessment, and expand onboarding of credit-invisible MSMEs while improving portfolio quality.

## The one-line north star
*Not* a scoring dashboard. An **agent that owns the credit-invisible-MSME underwriting workflow** — ingest → decide → act → log — with a human-in-the-loop approval gate that makes autonomy safe to buy.

## How to use this pack

| # | File | What it's for | Read when |
|---|------|---------------|-----------|
| 01 | `01-idea-agentic-reframe.md` | Why this is an agentic OS, not a wrapper; the loop, the moat, the wedge | First — it's the conceptual contract everything else serves |
| 02 | `02-architecture.md` | The full system architecture: deep-agent topology, knowledge brain, governance layer, tech mapping | Before you write any code |
| 03 | `03-agent-specs.md` | Per-subagent contracts: I/O, MCP tools, Deep Agents subagent config, guardrails, HITL gate | When implementing each agent |
| 04 | `04-scoring-model.md` | The Financial Health Score: dimensions, features, ML approach, SHAP explainability, thin-file confidence | When building the decisioning core |
| 05 | `05-data-and-integrations.md` | Data sources, connectors, MCP contracts, the Docling→CocoIndex→GBrain knowledge brain, consent/DPDP | When wiring data + integrations |
| 06 | `06-build-plan-and-demo.md` | 24-day plan, golden demo path, MVP cut line, role split, selection deck + Q&A | For sequencing the build and winning the pitch |
| 07 | `07-agentic-capabilities.md` | The Deep Agents capability + storage map (planning, subagents, virtual FS, memory, HITL, permissions) | When configuring the agent harness — and to make the "agentic OS" claim concrete |

## Stack at a glance
- **Agent harness:** Deep Agents (`deepagents`) on the **LangGraph** runtime — planning, subagents, virtual filesystem + memory store, human-in-the-loop, permissions.
- **Tools/integrations:** **MCP** servers per external system (AA, GST, UPI, EPFO, LOS, OCEN/ULI, score model).
- **Knowledge brain:** **Docling** (parse) → **CocoIndex** (incremental index) → **GBrain** (read/write agentic knowledge graph).
- **Decisioning:** deterministic, versioned ML model (XGBoost + SHAP) — never an LLM.
- **Deferred (later, clean seams):** Temporal (durability at scale), A2A (cross-org federation).

## Guiding principles (true across every doc)
1. **The score is deterministic and auditable; the LLM never does the credit math.** LLMs orchestrate, reconcile, and explain — a versioned ML model decides. A bank cannot deploy a black-box credit decision.
2. **Guardrails are the product, not overhead.** HITL approval, scoped permissions, immutable audit, explainability, sandboxing — these are what make an autonomous credit agent buyable.
3. **Own the workflow, not a step.** The defensible thing is running onboarding-to-monitoring end to end, not computing a number.
4. **The hard last mile is the moat.** Thin files, conflicting data across GST/bank/UPI, fraud/gaming, regulatory explainability — solve the ugly 20% and you can't be copied by a generalist.
5. **Sandbox-ready by design.** Connectors are clean swappable interfaces: synthetic data now, IDBI sandbox APIs the day you're shortlisted.
6. **Lean on the harness; build only the substance.** Deep Agents + LangGraph give planning, subagents, storage, and HITL for free — spend your scarce time on the scoring/reconciliation core and the knowledge brain, not on re-inventing orchestration.

## Status / assumptions
- Verify the official IDBI Innovate 2026 submission checklist + deadline against the real event page; the "24 days" and submission format below are planning assumptions.
- All data integrations are adapter-mocked against synthetic data until sandbox access is granted; the architecture is designed for that swap to be a config change, not a rewrite.
