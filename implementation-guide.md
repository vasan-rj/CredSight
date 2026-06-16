# Implementation Guide — Path to Bankability + Learning Loop

Two differentiators that turn CredSight from a single-pass workflow into an **agentic OS** that
closes the loop:

```
Ingest → Decide → Act → Update → Audit → Improve → Loop
                         └────── D2: Learning Loop ──────┘
   D1: Path to Bankability sits on Decide — it develops the borrower, not just judges them.
```

- **D1 — Path to Bankability**: for a sub-band MSME, compute the shortest realistic, borrower-
  controllable changes that cross the next band; show a dated action plan. Develops the *borrower*.
- **D2 — Learning Loop**: capture every human decision/override, detect patterns, and propose
  versioned recalibration to the risk team. Develops the *model + policy*.

Design source of truth (rationale, alternatives, review): `~/.gstack/projects/India_runs/vasan-main-design-20260614-200645.md`.
This guide is in sync with that doc — both cover D1 + D2; the dossier is a stretch (Approach B);
"agent theater" (Approach C) was considered and dropped (fragile, less differentiating).

## Non-negotiable invariants (both features)

1. **The LLM never computes or alters the score.** Every number shown is a real
   `score_model.predict` output or a difference of two such outputs. LLM may only phrase labels,
   gated by the existing faithfulness check.
2. **No autonomous model mutation.** D2 *recommends* recalibration; a human approves, and every
   change bumps `model_version` and is audited. "Learns" ≠ "drifts."
3. **Honesty labels.** D1 projections are "projected — not a promise." D2 recommendations are
   "pending risk-team approval."
4. All data synthetic. No new external systems.

## Where things live (verified symbols)

| Symbol | File | Use |
|---|---|---|
| `predict(fv) -> ScoreResult` | `src/credsight/scoring/model.py` | scoring entry; auto-selects GBM vs dimension basis |
| `_weighted_composite(dims)` | `scoring/model.py` | private; re-export or import directly in pathways.py |
| `compute_dimensions(fv)` | `scoring/dimensions.py` | D1 monotonic basis |
| `compute_confidence(fv)` | `scoring/confidence.py` | thin-file confidence |
| `FeatureVector`, `ScoreResult`, `Dimension`, `DIMENSION_WEIGHTS`, `SCORE_MIN/MAX`, `ShapDriver` | `scoring/schema.py` | contracts |
| `record_decision(app, decision, reason, underwriter)` | `service/pipeline.py` | **D2 Update hook** (`underwriter` has default) |
| `ApplicationStore` (get/all/put) | `service/store.py` | persistence |
| `Application` | `service/models.py` | application dataclass |
| `brain.capture(note, tags)`, `brain.search(...)` | `knowledge/brain.py` | **D2 Improve write-back** (works today) |
| `resume_assessment(app_id, decision, reason, underwriter)` | `agents/run.py` | resume after HITL |
| REST endpoints (`/api/...`) | `api/app.py`, `api/schemas.py` | UI surface |
| `frontend/src/types.ts`, `api.ts`, `components/` | frontend | Ledger UI |

---

# Part 1 — D1: Path to Bankability

## 1.1 Pin the actionable features (config)

Open one generated `data/synthetic/MSME*.json` and read `compute_dimensions` to learn the real
feature keys. Then in the new module define:

```python
# scoring/pathways.py  — all constants documented + versioned (auditable, like DIMENSION_WEIGHTS)
# Imports (actual module locations):
#   from .dimensions import compute_dimensions
#   from .model import _weighted_composite, predict
#   from .schema import FeatureVector, ScoreResult, SCORE_MIN

# Band floors, single source of truth (mirror HealthCard bands).
BANDS = [(750, "Strong"), (680, "Good"), (600, "Fair"), (SCORE_MIN, "Refer")]

@dataclass(frozen=True)
class Actionable:
    signed_step: float     # +raise / -lower per realistic improvement (e.g. emi_to_inflow_ratio is negative)
    max_value: float       # clamp cumulative steps to a realistic ceiling
    timeframe_days: int
    plain_label: str

ACTIONABLE: dict[str, Actionable] = {
    # All keys from scoring/dimensions.py (verified):
    "gst_filing_punctuality": Actionable(+0.15, 1.0,  90,  "File GST on time for 2 more quarters"),
    "gst_filing_continuity":  Actionable(+0.10, 1.0,  90,  "Resume consistent GST filing"),
    "inflow_regularity":      Actionable(+0.12, 1.0,  60,  "Route more sales through your bank/UPI"),
    "inflow_outflow_ratio":   Actionable(+0.20, 1.5,  60,  "Improve cash surplus relative to spend"),
    "balance_volatility_norm":Actionable(-0.15, 0.0,  90,  "Reduce extreme balance swings"),
    "bounce_rate":            Actionable(-0.10, 0.0,  90,  "Clear bounces, keep 3 months clean"),
    "obligation_servicing_ratio": Actionable(+0.10, 1.0, 60, "Regularise EMI/loan repayments"),
    "emi_to_inflow_ratio":    Actionable(-0.10, 0.0,  120, "Reduce EMI load relative to inflows"),
    "epfo_formality_proxy":   Actionable(+0.05, 1.0,  180, "Register employees under EPFO"),
    # Calibrate step sizes + timeframes against synthetic feature distributions.
}

# NEVER suggested — borrower cannot change these on demand:
NON_ACTIONABLE = {"gst_vintage_years", "operational_stability", "gst_turnover_trend", "sector"}
```

> **Sign convention confirmed (resolved):** `ShapDriver.direction == "negative"` ↔ `shap_value < 0`
> = feature below the 50 baseline = dragging composite down. `d.direction == "negative"` in
> `compute_path` candidates is the right filter. No runtime check needed.

## 1.2 The counterfactual engine

```python
# scoring/pathways.py

class PathStep(BaseModel):
    feature: str
    plain_label: str
    marginal_delta: int     # recomputed predict delta, in applied order
    timeframe_days: int

class Pathway(BaseModel):
    app_id: str
    basis: str              # "dimension" (monotonic) — what we ordered on
    current_composite: int
    target_band: str
    projected_composite: int
    projected_band: str
    reachable: bool
    steps: list[PathStep]
    disclaimer: str = "Projected by the deterministic model — guidance, not a promise."

def _apply_step(fv: FeatureVector, feat: str) -> FeatureVector:
    """Return a copy of fv with one feature improved by its configured signed_step,
    clamped to max_value. signed_step > 0 → max_value is ceiling; < 0 → floor."""
    cfg = ACTIONABLE[feat]
    current = fv.features.get(feat, 0.0)
    new_val = current + cfg.signed_step
    new_val = min(cfg.max_value, new_val) if cfg.signed_step > 0 else max(cfg.max_value, new_val)
    return fv.model_copy(update={"features": {**fv.features, feat: new_val}})

def _dimension_composite(fv: FeatureVector) -> int:
    # monotonic basis: same transforms the Health Card shows
    return _weighted_composite(compute_dimensions(fv))

def compute_path(fv: FeatureVector, score: ScoreResult) -> Pathway:
    current = score.composite
    target_floor, target_band = _next_band_floor(current)        # from BANDS
    if target_floor is None:                                     # already top band
        return Pathway(..., reachable=True, steps=[], target_band="Strong")  # "maintain"

    # candidates = negative-to-composite SHAP  ∩  ACTIONABLE keys
    candidates = [d.feature for d in score.shap
                  if d.direction == "negative" and d.feature in ACTIONABLE]

    chosen, working = [], deepcopy(fv)
    base = _dimension_composite(working)
    while _dimension_composite(working) < target_floor:
        best = None  # (feature, trial_fv, marginal_delta)
        for feat in candidates:
            if feat in {s.feature for s in chosen}:              # one step per feature (or until max_value)
                continue
            trial = _apply_step(working, feat)                   # signed_step, clamped to max_value
            delta = _dimension_composite(trial) - _dimension_composite(working)
            if delta > 0 and (best is None or delta > best[2]):  # skip non-positive; pick max marginal
                best = (feat, trial, delta)
        if best is None:                                         # nothing improves → unreachable
            break
        feat, working, delta = best
        cfg = ACTIONABLE[feat]
        chosen.append(PathStep(feature=feat, plain_label=cfg.plain_label,
                               marginal_delta=delta, timeframe_days=cfg.timeframe_days))

    projected = _dimension_composite(working)
    # Basis-binding: validate the crossing on the ACTUAL decision composite (GBM if trained),
    # so the projection binds the real gate — not only the dimension basis we ordered on.
    decision_projected = predict(working).composite
    reachable = decision_projected >= target_floor
    return Pathway(app_id=fv.app_id, basis="dimension", current_composite=current,
                   target_band=target_band, projected_composite=decision_projected,
                   projected_band=_band_of(decision_projected), reachable=reachable, steps=chosen)
```

Key rules baked in (all from the reviewed design):
- **Order on the monotonic dimension basis** so steps are always sensible.
- **Skip any step whose delta ≤ 0** → no "file more GST → −7 pts" ever reaches the UI.
- **Validate the final crossing on `predict().composite`** (the real decision composite) so the
  "you'd cross the floor" claim binds the actual gate.
- **`max_value` clamp** + **`signed_step` direction** handle ceilings and "reduce this" steps.
- Claim "a short, ordered set," never "the smallest" (greedy approximates over interacting features).

## 1.3 Expose it

- `service/pipeline.py` (or `agents/run.py`): after scoring, if the run is **below the product band
  floor** (`eligible == false`/`out_of_policy` by band), attach `pathway = compute_path(fv, score)`
  to the result. Skip for confidence-only flags (band is fine → would mislead).
- `api/app.py`: add `GET /api/applications/{app_id}/pathway` **or** fold `pathway` into the
  orchestrator `RunResult`. Prefer folding in — one fewer round trip for the demo.

## 1.4 Frontend types + client

- `frontend/src/types.ts`: add `PathStep`, `Pathway`; add `pathway?: Pathway | null` to `RunResult`.
- `frontend/src/api.ts`: nothing if folded into `RunResult`; else add `getPathway(appId)`.
- `frontend/src/mock.ts`: add a sample `pathway` so `USE_MOCK` demos it.

## 1.5 Frontend panel

`frontend/src/components/PathToBankability.tsx` — render on the Health Card, **only when
`run.pathway` exists and the run is sub-band**. Ledger system (reuse `Ring`, `Chip`, `Card`,
`SectionLabel` from `components/ui.tsx`):

- Target-band ring delta: small current ring → arrow → projected ring (612 → ~686).
- Step rows: `plain_label` · emerald `+{marginal_delta}` chip · mono `~{timeframe_days}d`.
- `reachable === false` → honest empty state: "No borrower-controllable path to the next band right
  now — an officer can review your case." Never a fake/zero-step plan.
- Top-band run → one "maintain" line.
- Always show the `disclaimer`. Panel title "Raise your score," not "Get approved."

## 1.6 Tests + eval

- `tests/` unit: faithfulness (displayed `+pts` == recomputed marginal), **no negative-delta step
  surfaced**, archetype regression (thin_file reachable; strong → no path; stressed → measured,
  empty state if unreachable), monotonic/non-decreasing accumulation.
- `scoring/eval.py`: add a **path-faithfulness** metric so CI guards it like explanation faithfulness.

---

# Part 2 — D2: Learning Loop

The honest, bank-safe loop. Four arrows: **Update → (Audit) → Improve → Loop.**

## 2.1 Update — persist decisions + overrides

`record_decision()` is the hook. Add a structured outcomes log alongside the audit (audit stays the
immutable narrative; this is the queryable signal).

```python
# service/outcomes.py
class DecisionOutcome(BaseModel):
    app_id: str
    ts: str
    segment: str                 # sector / archetype / band bucket
    model_recommendation: str    # "offer" | "refer" | "reject"
    human_decision: str          # "approve" | "override" | "request_info"
    override: str | None         # "up" (approved a refer/reject) | "down" (rejected an offer) | None
    reason: str
    model_version: str

def log_outcome(o: DecisionOutcome) -> None: ...      # append (JSONL or store table)
def query(segment: str | None = None, days: int = 30) -> list[DecisionOutcome]: ...
```

In `record_decision()` / `resume_assessment()`: compute `override` by comparing the human decision
to `model_recommendation`, then `log_outcome(...)`. No behavior change to the decision itself.

## 2.2 Improve — detect patterns, recommend recalibration

```python
# governance/learning.py
class RecalRecommendation(BaseModel):
    segment: str
    pattern: str                 # e.g. "12 thin-file kirana overrides UP in 30 days"
    suggestion: str              # e.g. "raise HITL floor for thin-file, or +weight cash_flow"
    evidence_count: int
    status: str = "pending_human_approval"

def scan(window_days: int = 30, threshold: int = 8) -> list[RecalRecommendation]:
    # group outcomes by segment; when overrides in one direction exceed threshold, emit a rec
    ...
    for rec in recs:
        brain.capture(f"{rec.pattern} → {rec.suggestion}",
                      tags=["learned-pattern", rec.segment])   # write-back; index refreshes
    return recs
```

This is the piece that was **missing** today (`brain.capture` existed but was never called). Now an
override pattern → a captured learning + a recommendation. **It never changes the model itself.**

## 2.3 Versioned recalibration (human-approved)

A human action, not automatic:
- Risk team reviews a `RecalRecommendation`, approves → adjust `DIMENSION_WEIGHTS` / HITL floor in
  config, re-run `credsight-train`, bump `config.score_model_version`.
- Record the change (old → new version, what changed, who approved) — auditable model governance.
- For the demo without real outcomes: show the recommendation + a `model_version` history with the
  diff. The mechanism is real; the trigger (real repayment labels) is the only synthetic part.

## 2.4 Loop — monitoring re-score

`agents/subagents.py` already has the monitoring stub. On a tick (or a demo "advance time" button):
re-`predict` stored MSMEs, flag band drift, and feed that + new outcomes back into 2.1/2.2. Read-only;
alerts are recommendations.

## 2.5 Surface — the "Learning" view

New tab in `frontend/src/App.tsx` (`learning`) + `components/LearningLoop.tsx` (Ledger style):
- **This cycle**: N decisions captured, M overrides (split up/down) — from `outcomes.query`.
- **Patterns detected**: each `RecalRecommendation` as a card, `evidence_count`, `pending` chip.
- **Model version history**: timeline of versions with what changed + approver (reuse the audit
  timeline component pattern).
- Endpoints: `GET /api/learning/summary`, `GET /api/learning/recommendations`,
  `POST /api/learning/recommendations/{id}/approve` (records approval; demo bumps version).

## 2.6 Tests

- `override` classification correct for each (recommendation, human-decision) pair.
- `scan` emits a rec only past threshold; `brain.capture` called with the expected tags.
- Approving a rec writes an audit event and bumps `model_version`; **no path mutates the model
  without an approval** (assert).

---

# Part 3 — GBrain: a clause-linked knowledge graph + real self-organize cycle

Today GBrain is a flat searchable index and `organize()` is a stub returning a count. Make it a real
**knowledge graph** — clauses are nodes, typed links connect them — with a working **self-organize
("dream") cycle** that dedupes, links, clusters, promotes, and flags. This is the engine behind D2's
*Improve* arrow: `capture()` writes a learned clause, and the dream cycle wires it into the graph so
"the system learns" is visibly true (the graph grows and self-wires), not a flat append.

Bank-safe by construction: operator policy is **read-only** to the cycle; it only reorganizes the
learned layer + edges + tags; contradictions go to humans; every merge/promotion is reversible via
provenance; **no LLM invents links** (LLM may only phrase an edge's description, gated).

## 3.1 Graph data model (extend `knowledge/models.py`)

`PolicyClause` stays the retrieval DTO. Add the graph projection:

```python
@dataclass(frozen=True)
class ClauseNode:
    ref: str                  # = PolicyClause.ref (node id)
    title: str
    text: str
    source: str
    segment: str | None
    kind: str                 # "policy" | "learned"
    support: int = 1          # times observed / co-cited
    community_id: str | None = None
    status: str = "active"    # "active" | "quarantined" | "superseded"
    created_ts: str = ""
    last_seen_ts: str = ""

@dataclass(frozen=True)
class ClauseEdge:
    src: str; dst: str
    type: str                 # see edge types below
    weight: float
    provenance: str           # how derived (regex / similarity / co-citation / segment)
    created_ts: str = ""
```

**Edge types:** `refines`, `exception_to`, `supersedes`, `contradicts`, `similar_to` (semantic),
`co_cited` (used together for one decision), `derived_from` (learned ← policy), `same_segment`.

## 3.2 Graph store (`knowledge/graph.py`, dependency-free default, pluggable like the index)

Markdown stays source of truth; the graph is a **derived sidecar** — `knowledge/graph/nodes.jsonl` +
`edges.jsonl` (git-diffable, operator-inspectable). Rebuilt by `organize()`, never the master copy.

```python
class ClauseGraph:
    def load(self) / save(self)
    def add_edge(self, e: ClauseEdge)        # dedup on (src,dst,type): keep max weight, merge provenance
    def neighbors(self, ref, types=None, depth=1) -> list[ClauseNode]
    def nodes(self) / edges(self)
    def to_json(self) -> dict                # nodes + edges + communities (for the UI)
    def to_html(self) -> str                 # graphify-style: nodes colored by community, typed edges
```

## 3.3 Edge construction — four signal sources (all rule/score-backed)

- **(a) Explicit references** in clause text — `see §X`, `notwithstanding §Y`, supersede/exception
  markers → `refines` / `exception_to` / `supersedes` (regex over the Markdown).
- **(b) Semantic similarity** — cosine on the `pgvector` backend, else shared-IDF lexical overlap on
  `LexicalIndex` (reuse `_tokens`/`_score`), above `sim_threshold` → `similar_to` (weight = score).
- **(c) Co-citation** — clauses returned together by `knowledge.search` for the same decision
  (`policy_clause_refs` in the audit log / D1+D2 outcomes) → `co_cited` (weight = co-occurrence count).
- **(d) Shared segment** metadata → `same_segment` (cheap backbone).
- **Contradiction** — a learned clause whose claim opposes a policy clause on the same segment
  (opposing condition + same segment) → `contradicts` (**flag, never auto-resolve**).

## 3.4 The real self-organize cycle (`knowledge/organize.py`; `brain.organize()` calls it)

Deterministic, incremental (CocoIndex-style: reprocess only changed files), **idempotent** (running
twice on an unchanged corpus yields an identical graph):

1. **Re-chunk** changed docs → refresh node set (reuse `index._chunk` / `refresh`).
2. **Dedupe/merge** near-duplicate *learned* clauses (similarity ≥ `merge_threshold`): one node, summed
   `support`, provenance kept. **Never merges policy nodes.**
3. **(Re)build typed edges** from 3.3 (a–d) — recomputed from scratch each cycle → idempotent.
4. **Community detection** — Louvain if `python-louvain` present, else deterministic label-propagation
   (fixed tie-break) → `community_id`. Same philosophy as `/graphify`'s clustered communities.
5. **Promote / decay** — learned node with `support ≥ promote_threshold` and recent `last_seen` →
   `active`; stale + low-support → `quarantined`. Mirrors the capture quarantine→active idea.
6. **Contradiction flags** — emit `contradicts` edges + a human-review item (reuse D2's
   `RecalRecommendation` channel). Never deletes a policy clause.
7. **Emit `OrganizeReport`** `{added, merged, edges_by_type, communities, promoted, quarantined,
   flagged}` → append `knowledge/graph/organize-log.jsonl` + return; surface in the UI.

Thresholds (`merge_threshold`, `sim_threshold`, `promote_threshold`, `decay_days`) are documented
constants in `organize.py`, like `DIMENSION_WEIGHTS` (auditable).

## 3.5 Graph-aware retrieval (upgrade `brain.search`)

After the base lexical/semantic match, **expand 1 hop** along `refines` / `exception_to` /
`supersedes` / `contradicts` edges and include those neighbors (deduped, re-ranked). The agent then
cites the **full applicable cluster** — the rule *and* its exception *and* any superseding learned
clause — satisfying the grounding rule ("cite every applicable clause"). `superseded` nodes are
excluded; `contradicts` neighbors are surfaced for the audit rationale.

## 3.6 Surface (frontend)

- **"Knowledge Graph"** view (or a panel in the Learning tab): interactive nodes colored by
  community, typed edges; click a node → its clause + neighbors; show the latest `OrganizeReport`
  (what the last dream cycle did). Reuse the `/graphify` HTML/JSON style if available.
- Endpoints: `GET /api/knowledge/graph` (nodes + edges + communities), `POST /api/knowledge/organize`
  (run the cycle; admin/cron/demo button) → returns `OrganizeReport`.

## 3.7 Scheduling / CLI

- `credsight-organize` entry in `pyproject.toml [project.scripts]` → runs `organize()` once; intended
  as a nightly cron ("dream" cycle).
- Demo: a **"Run dream cycle"** button hitting `POST /api/knowledge/organize`, so judges *watch the
  graph self-wire* right after a `capture()` from the Learning Loop.

## 3.8 Tests

- Each edge source (a–d) produces the expected edge type on fixtures (regex refs; co-citation from a
  synthetic audit log; similarity threshold).
- **`organize` idempotency**: run twice on unchanged corpus → identical graph.
- Dedupe merges duplicates + preserves provenance; **never merges/mutates policy nodes**.
- Promotion/decay thresholds; contradiction **flagged, not auto-resolved**; `knowledge/policies/`
  never written by the cycle (assert).
- `search` edge-expansion returns the cluster (rule + exception); `superseded` excluded.
- Community detection deterministic (fixed seed / LPA tie-break).

> **D2 link:** the Learning Loop's `brain.capture()` (Part 2 §2.2) is the *writer*; this self-organize
> cycle is the *Improve* engine that wires the learned clause into the graph, links it to the policy it
> refines or contradicts, and surfaces contradictions for human review. Together they make the
> Improve→Loop arrows real and visible.

# Build order (sequenced; each step independently demoable)

1. **D1.1 + D1.2** — `scoring/pathways.py` + actionable config + unit tests. *Checkpoint: `compute_path`
   returns a sensible, faithful, non-decreasing path for the thin_file archetype.*
2. **D1.3 + D1.4** — wire `pathway` into `RunResult` + types/mock. *Checkpoint: API returns it.*
3. **D1.5** — `PathToBankability` panel. *Checkpoint: Lakshmi → Health Card → dated plan, <60s demo.*
4. **D1.6** — path-faithfulness eval in CI.
5. **D2.1** — `service/outcomes.py` + log in `record_decision`. *Checkpoint: overrides recorded.*
6. **D2.2** — `governance/learning.py` scan → `brain.capture` + recommendations. *Checkpoint: an
   override pattern produces a captured learning.*
7. **D2.5** — Learning view + endpoints. *Checkpoint: judges see "what the system learned this cycle."*
8. **P3.1–3.4** — `ClauseNode`/`ClauseEdge` + `graph.py` store + edge construction + real `organize()`
   cycle, replacing the stub. *Checkpoint: `credsight-organize` builds nodes.jsonl/edges.jsonl with
   typed links + communities; idempotent on a second run.*
9. **P3.5** — graph-aware `search` (1-hop edge expansion). *Checkpoint: a query returns the rule + its
   exception together; audit cites the full cluster.*
10. **P3.6 + P3.7** — `/api/knowledge/graph` + `/api/knowledge/organize`, Knowledge Graph view, "Run
    dream cycle" button. *Checkpoint: capture a learning → run dream cycle → graph self-wires on screen.*
11. **D2.3 + D2.4** — version-history + monitoring re-score (stretch / if time).
12. **(Stretch) Decision Dossier** — one-click export reusing audit + SHAP + policy refs.

# Guardrails checklist (verify before demo)

- [ ] No LLM call sits in the score or pathway math; every `+pts` is a `predict` difference.
- [ ] No negative-delta step can render (asserted).
- [ ] Pathway crossing validated on the real decision composite, not only the dimension basis.
- [ ] D2 never mutates `DIMENSION_WEIGHTS` / model without a recorded human approval + version bump.
- [ ] All projections/recommendations carry honesty labels.
- [ ] Strong archetype shows no false path; confidence-only flags show no band path.
- [ ] **`organize()` never writes `knowledge/policies/`** (operator policy read-only); the graph is a
      derived sidecar, Markdown stays source of truth.
- [ ] **No LLM invents graph edges**; contradictions are flagged to humans, never auto-resolved.
- [ ] `organize()` is idempotent on an unchanged corpus (asserted).
- [ ] `frontend/src/api.ts` `USE_MOCK = false` committed; mock carries sample `pathway` + learning +
      graph data.

# Verification

```bash
# backend
pip install -e ".[dev]" && pytest -q && credsight-eval        # path-faithfulness must pass
credsight-organize                                            # build/refresh the clause graph (dream cycle)
credsight-organize                                            # run again → identical graph (idempotency)
credsight-api                                                 # :8000

# frontend
cd frontend && npm run lint && npm run dev                    # :5173
# Demo arc: Lakshmi (thin file) → Health Card → Path to a better offer →
#           approve/override in Console → Learning view shows the captured pattern →
#           Run dream cycle → Knowledge Graph self-wires (new clause linked to the policy it refines).
```
