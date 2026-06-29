"""Path-to-Bankability (D1): shortest set of borrower-controllable changes to cross the
next composite band. All arithmetic is deterministic model calls — no LLM in the math.

The LLM never touches the step sizes, deltas, or the reachability claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel

from .dimensions import compute_dimensions
from .model import _weighted_composite, predict
from .schema import SCORE_MIN, FeatureVector, ScoreResult

# ── Band table — mirrors policy.py and ui.tsx band() exactly ─────────────────
# Ordered high→low: (floor, label)
BANDS: list[tuple[int, str]] = [
    (750, "Strong"), (680, "Good"), (600, "Fair"), (SCORE_MIN, "Refer")
]


# ── Actionable feature config ─────────────────────────────────────────────────
@dataclass(frozen=True)
class Actionable:
    signed_step: float      # amount to change the raw feature value per step
    max_value: float        # ceiling (step > 0) or floor (step < 0)
    timeframe_days: int
    plain_label: str


# Keys verified against scoring/dimensions.py — all are real FeatureVector.features keys.
ACTIONABLE: dict[str, Actionable] = {
    "gst_filing_punctuality":     Actionable(+0.15, 1.0,  90,  "File GST on time for 2+ quarters"),
    "gst_filing_continuity":      Actionable(+0.10, 1.0,  90,  "Resume consistent GST filing"),
    "inflow_regularity":          Actionable(+0.12, 1.0,  60,  "Route more sales through bank/UPI"),
    "inflow_outflow_ratio":       Actionable(+0.15, 1.5,  60,  "Improve cash surplus vs spend"),
    "balance_volatility_norm":    Actionable(-0.15, 0.0,  90,  "Reduce extreme balance swings"),
    "bounce_rate":                Actionable(-0.10, 0.0,  90,  "Clear bounces, 3 clean months"),
    "obligation_servicing_ratio": Actionable(+0.10, 1.0,  60,  "Regularise loan repayments"),
    "emi_to_inflow_ratio":        Actionable(-0.10, 0.0,  120, "Reduce EMI load vs inflows"),
    "epfo_formality_proxy":       Actionable(+0.05, 1.0,  180, "Register employees under EPFO"),
}

# Dimension name → constituent raw feature keys (for pseudo-SHAP fallback where SHAP
# features are dimension names, not raw feature names).
_DIM_FEATURES: dict[str, list[str]] = {
    "cash_flow_health":           ["inflow_regularity", "inflow_outflow_ratio", "balance_volatility_norm"],
    "gst_turnover_signal":        ["gst_filing_punctuality", "gst_filing_continuity"],
    "banking_discipline":         ["bounce_rate", "obligation_servicing_ratio"],
    "business_vintage_stability": [],   # non-actionable
    "obligation_load_formality":  ["emi_to_inflow_ratio", "epfo_formality_proxy"],
}


# ── Pathway data model ────────────────────────────────────────────────────────
class PathStep(BaseModel):
    feature: str
    plain_label: str
    marginal_delta: int     # composite pts gained by this step (always > 0)
    timeframe_days: int


class Pathway(BaseModel):
    app_id: str
    basis: str = "dimension"   # monotonic dimension composite used for step ordering
    current_composite: int
    target_band: str
    projected_composite: int
    projected_band: str
    reachable: bool
    steps: list[PathStep]
    disclaimer: str = "Steps shown in application order. Each delta reflects improvement after prior steps applied. Guidance, not a promise."


# ── Private helpers ───────────────────────────────────────────────────────────
def _next_band_floor(composite: int) -> tuple[Optional[int], str]:
    for floor, label in BANDS:
        if composite < floor:
            return floor, label
    return None, BANDS[0][1]


def _band_of(composite: int) -> str:
    for floor, label in BANDS:
        if composite >= floor:
            return label
    return BANDS[-1][1]


def _dimension_composite(fv: FeatureVector) -> int:
    """Monotonic dimension basis — same transforms the Health Card shows."""
    return _weighted_composite(compute_dimensions(fv))


def _apply_step(fv: FeatureVector, feat: str) -> FeatureVector:
    """Apply one configured step to a single feature, clamped to max_value."""
    cfg = ACTIONABLE[feat]
    current = fv.features.get(feat, 0.0)
    new_val = current + cfg.signed_step
    new_val = min(cfg.max_value, new_val) if cfg.signed_step > 0 else max(cfg.max_value, new_val)
    return fv.model_copy(update={"features": {**fv.features, feat: new_val}})


def _candidates(score: ScoreResult) -> list[str]:
    """Derive candidate features from SHAP drivers. Bridges dimension-level SHAP (the
    pseudo-SHAP fallback that uses dimension names) to raw feature keys; falls back to
    full ACTIONABLE list when nothing is negative."""
    result: list[str] = []
    for d in score.shap:
        if d.direction != "negative":
            continue
        if d.feature in ACTIONABLE:
            result.append(d.feature)
        elif d.feature in _DIM_FEATURES:
            result.extend(f for f in _DIM_FEATURES[d.feature] if f in ACTIONABLE)
    return result or list(ACTIONABLE)


# ── Main entry point ──────────────────────────────────────────────────────────
def compute_path(fv: FeatureVector, score: ScoreResult) -> Pathway:
    """Greedy path to the next composite band.

    Orders steps on the monotonic dimension basis (so each chosen step is guaranteed
    to improve the dimension composite). Validates the final band-crossing claim on
    the full decision composite (predict()) so the "you'd cross the floor" claim
    binds the actual gate, not just the ordering heuristic."""
    current = score.composite
    target_floor, target_band = _next_band_floor(current)

    if target_floor is None:  # already Strong — return a maintenance path
        return Pathway(
            app_id=fv.app_id, current_composite=current, target_band=BANDS[0][1],
            projected_composite=current, projected_band=_band_of(current),
            reachable=True, steps=[],
        )

    candidates = _candidates(score)
    chosen: list[PathStep] = []
    working = fv.model_copy()

    while _dimension_composite(working) < target_floor:
        best: tuple[str, FeatureVector, int] | None = None
        for feat in candidates:
            if feat in {s.feature for s in chosen}:
                continue
            trial = _apply_step(working, feat)
            delta = _dimension_composite(trial) - _dimension_composite(working)
            if delta > 0 and (best is None or delta > best[2]):
                best = (feat, trial, delta)
        if best is None:
            break   # no actionable feature improves the score → unreachable
        feat, working, delta = best
        cfg = ACTIONABLE[feat]
        chosen.append(PathStep(
            feature=feat, plain_label=cfg.plain_label,
            marginal_delta=delta, timeframe_days=cfg.timeframe_days,
        ))

    # Validate crossing on the REAL decision composite (may differ from dimension basis
    # once the calibrated XGBoost is in place).
    decision_projected = predict(working).composite
    reachable = decision_projected >= target_floor
    return Pathway(
        app_id=fv.app_id, current_composite=current, target_band=target_band,
        projected_composite=decision_projected, projected_band=_band_of(decision_projected),
        reachable=reachable, steps=chosen,
    )
