# 07 — Agentic Capabilities & Storage (Deep Agents)

*Explicitly surfaces the agentic features CredSight stands on — especially how it **stores** state and knowledge. All of this is built into the Deep Agents harness (on the LangGraph runtime), so we configure it rather than build it. Use this doc to make the "agentic OS" claim concrete in code and in the pitch.*

---

## The capability map

| Deep Agents capability | What it gives us | Where CredSight uses it |
|---|---|---|
| **Planning — `write_todos`** | Decompose a task into tracked steps; adapt as new info arrives | Orchestrator breaks each application into a visible plan (great demo beat) |
| **Subagents — `task` tool** | Spawn specialists in isolated context windows; async for background work | Each specialist (ingestion, reconciliation, scoring, …) is a subagent; the monitor is async |
| **Virtual filesystem (pluggable backends)** | Store working data as files instead of bloating the prompt; swap backend (in-memory / disk / LangGraph store / custom) | Working memory per application (canonical data, features, recon notes, audit log) |
| **Long-term memory store** | Persist facts across threads/sessions | MSME profiles, prior assessments, underwriter override history |
| **Context compression / summarization** | Offload large tool results to files + summarize old turns | Long underwriting runs stay within the context window |
| **Human-in-the-loop (interrupt)** | Pause for human approval on sensitive tools | The credit-decision approval gate |
| **Filesystem + tool permissions** | Least-privilege read/write per file/dir/tool; subagents inherit or override | Only the action subagent can move money; ingestion is read-only |
| **Skills** | Reusable, packaged domain workflows + instructions | e.g. "assess thin-file micro-enterprise", "reconcile GST vs bank" |
| **Smart default prompts** | Plan-before-acting, verify-work behavior out of the box | Baseline reliability for every subagent |
| **LangGraph runtime** | Durable execution, checkpointing, streaming, interrupts | Crash-safe, resumable runs; powers the HITL pause |

## The three storage tiers (the part the brief asks us to show)

```
┌─ Per-run working memory ── Virtual filesystem (backend = LangGraph store) ─────────────┐
│   canonical/{app}.json · features/{app}.json · recon/{app}.md · audit/{app}.log         │
│   purpose: keep context lean; give the demo a visible agent "scratchpad"                │
└─────────────────────────────────────────────────────────────────────────────────────────┘
┌─ Cross-run memory ──────── Long-term memory store ─────────────────────────────────────┐
│   MSME profiles · prior assessments · override history                                  │
│   purpose: re-applications & monitoring build on history, not a cold start              │
└─────────────────────────────────────────────────────────────────────────────────────────┘
┌─ Shared domain brain ───── GBrain (Docling + CocoIndex feed it) ───────────────────────┐
│   policy clauses · sector norms · learned fraud patterns (agents read AND write)        │
│   purpose: self-improving, citable, always-fresh knowledge                              │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**Why three tiers, not one:** working memory is cheap and disposable (per application); long-term memory is per-MSME and durable; the knowledge brain is shared across all applications and self-organising. Conflating them is how agents either blow their context window or forget everything between runs.

## Minimal wiring (deepagents)
```python
from deepagents import create_deep_agent
from langgraph.store.memory import InMemoryStore   # swap for a persistent store in prod

# subagents declared in 03-agent-specs.md
orchestrator = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[*ingest_tools, knowledge_search, knowledge_capture,
           score_model_predict, *action_tools],
    system_prompt=UNDERWRITING_SYSTEM_PROMPT,
    subagents=[ingestion, reconciliation, scoring, explainability, action, monitoring],
    # filesystem backend persists per-run working files;
    # store=... persists long-term memory across threads;
    # human-in-the-loop configured on the money-moving action tools;
    # permission rules scope which subagents may read/write which files + tools.
)
```

## How to show it on stage (turns architecture into a winning beat)
- Show the **plan** (`write_todos`) appear as the agent decomposes the application — judges *see* it reasoning, not a black box.
- Show a subagent **write a file** to the virtual filesystem (the canonical data / reconciliation notes) — that's the "agent has a memory" moment.
- Hit the **HITL interrupt** live: the run pauses, the underwriter approves, the run resumes — the trust story.
- Open the **audit log** file + a GBrain entry the agent **captured** — "it learns and leaves a trail."

## What we deliberately deferred (and why it's safe to)
- **Temporal** — heavier, long-horizon, cross-service durability with SLAs/retries (e.g., fleet-scale monitoring). The LangGraph runtime covers durability for the challenge; Temporal slots in behind the same workflow seam later.
- **A2A** — cross-organisation agent federation. Not needed when all agents live in one harness; add it when CredSight must interoperate with external agentic systems.
Both are clean future swaps, not rewrites — call this out in the pitch as "deployment-aware sequencing," not a gap.
