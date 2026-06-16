# 04 — The Financial Health Score

*The decisioning core. This is the substance judges and the bank's risk team will probe, so it must be multidimensional, deterministic, and explainable. The LLM never computes any number here.*

---

## Design principles
1. **Deterministic & versioned.** A fixed feature pipeline + a versioned model → the same inputs always produce the same score, and any decision is reproducible months later. Banks cannot deploy non-reproducible credit logic.
2. **Multidimensional, not a single opaque number.** Five interpretable dimensions roll up into a composite, so strengths/risks are visible (the Health Card) and a regulator can follow the logic.
3. **Explainable by construction.** Every score ships with SHAP attributions and the policy clauses it was checked against.
4. **Honest about uncertainty.** A thin-file confidence indicator travels with the score; sparse data lowers confidence rather than fabricating certainty.

## The five dimensions
Each scored 0–100, then weighted into a composite scaled to a familiar **300–900** band.

| Dimension | Weight | What it captures | Primary sources |
|---|---|---|---|
| **Cash-flow health** | 30% | Inflow regularity, average balance, volatility, inflow/outflow ratio, seasonality | Bank (AA), UPI/QR |
| **GST & turnover signal** | 20% | Declared turnover trend, filing punctuality & continuity, input-tax behaviour | GST |
| **Banking discipline** | 20% | Cheque/mandate bounces, returns, overdraft behaviour, obligation servicing | Bank (AA) |
| **Business vintage & stability** | 15% | GST registration age, filing continuity, operational/address stability | GST, profile |
| **Obligation load / formality** | 15% | Existing EMI load vs inflow, leverage; EPFO as a scale/formality proxy | AA, EPFO, bureau |

> Weights are a defensible starting point — expose them as config and calibrate against synthetic outcome labels. Document any change (auditability).

## Feature examples per source (build the pipeline around these)
- **Bank (AA):** avg/median monthly balance, balance volatility (σ), count & ₹ of bounces, inflow regularity (coefficient of variation), top-counterparty concentration, salary/obligation debits.
- **UPI/QR:** monthly txn count & value, distinct payer count, day-of-week/seasonal pattern, growth trend, refund/reversal ratio, circular-flow flag (fraud signal).
- **GST:** turnover trend (QoQ), filing punctuality %, months filed / months registered, input-output ratio, nil-filing streaks.
- **EPFO:** active employee count, contribution continuity (a formality + scale proxy).
- **Bureau (if any):** existing obligations, DPD history — used when present, never required (NTC by definition often lacks it).
- **Cross-source (reconciliation):** GST-vs-bank turnover agreement ratio, UPI-vs-bank consistency — disagreement beyond tolerance lowers confidence and raises a flag.

## Modelling approach
- **Per-dimension sub-scores:** transparent, monotonic transforms / lightweight models on each dimension's features so each sub-score is independently explainable.
- **Composite:** a gradient-boosted model (XGBoost) over the dimension features for ranking power, **calibrated** (e.g., isotonic/Platt) so the composite maps to a meaningful risk band — plus the weighted-dimension view for interpretability. Show both: the GBM gives discrimination, the weighted view gives a regulator something to read.
- **Why not an LLM for scoring:** non-deterministic, non-reproducible, un-auditable, and prone to plausible-but-wrong arithmetic. The LLM's job is reconciliation reasoning + explanation, not the credit decision.
- **Eligibility mapping:** composite band → eligible product, amount range, indicative rate band, tenor — checked against credit-policy clauses retrieved from the knowledge brain (`knowledge.search`) before it becomes a recommendation.

## Explainability (SHAP + policy grounding)
- Run SHAP on the composite model → top positive and negative drivers, per applicant.
- The Explainability agent renders these as: MSME-facing ("Your GST filings are regular and turnover is up 12% — a strength. Frequent low balances late in the month pull your score down.") and underwriter-facing (structured drivers + policy refs + confidence).
- **Faithfulness rule:** generated language may reference only the actual top SHAP drivers and retrieved clauses — enforced programmatically, fails closed to a template.

## Thin-file confidence
A separate **confidence ∈ [0,1]** from: number of sources present, months of history, and cross-source agreement. Surface it on the Health Card and route low-confidence cases to the HITL gate. This is a differentiator — most teams will present a single number with false precision; you present a score *and how much to trust it*.

## Evaluation harness (run in CI from day one)
- **Decision quality:** against synthetic ground-truth labels (good/stressed/default archetypes) — AUC/KS for ranking, calibration error for the band mapping.
- **Explanation faithfulness:** % of generated explanations whose cited drivers match the model's actual top SHAP features (target ~100%).
- **Stability:** small input perturbations shouldn't swing the band (sanity for robustness).
- Keep three labelled synthetic archetypes — **thin-file, strong, stressed** — as fixed regression cases you re-run on every change.

## What to claim (and not claim) to judges
- **Do** claim: multidimensional, explainable, reproducible, policy-grounded, with honest confidence. Show the SHAP drivers live.
- **Don't** claim a magic accuracy number on synthetic data. If asked about accuracy, answer: "On synthetic archetypes we show strong ranking (AUC/KS) and calibrated bands; on your sandbox data we'd back-test against real outcomes — and crucially, every decision is explainable and human-approved, so it's safe to pilot before it's perfect." That framing beats any team waving an unverifiable percentage.
