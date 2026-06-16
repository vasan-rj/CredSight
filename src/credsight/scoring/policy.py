"""Eligibility mapping: composite band -> eligible product / amount / rate / tenor,
checked against credit-policy clauses retrieved from the knowledge brain (FR-12/13).

The band table here is a defensible default for the synthetic build. In production the
policy clauses come from GBrain (knowledge.search) and are CITED in the audit rationale;
out-of-policy decisions are forced to human review (governance/hitl.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from .schema import ScoreResult


@dataclass(frozen=True)
class EligibilityBand:
    lower: int  # inclusive composite floor
    product: str
    max_amount: float
    indicative_rate: float  # annual %
    max_tenor_months: int


# Coarse default bands for working-capital / unsecured small-ticket (the beachhead).
# Calibrate against synthetic labels; real bands come from policy docs via GBrain.
_BANDS: list[EligibilityBand] = [
    EligibilityBand(750, "Working capital (unsecured)", 500_000, 16.0, 36),
    EligibilityBand(680, "Working capital (unsecured)", 250_000, 18.0, 24),
    EligibilityBand(600, "Micro working capital", 100_000, 22.0, 18),
    EligibilityBand(300, "Refer / not eligible", 0, 0.0, 0),
]


@dataclass(frozen=True)
class Recommendation:
    app_id: str
    eligible: bool
    product: str
    amount: float
    indicative_rate: float
    tenor_months: int
    band_floor: int
    out_of_policy: bool = False
    policy_clause_refs: list[str] | None = None  # GBrain citations, for the audit trail


def recommend(score: ScoreResult) -> Recommendation:
    """Map a score to a recommendation. Always a *recommendation* — never an executed
    action. The HITL gate decides whether a human must sign off (FR-13)."""
    band = next(b for b in _BANDS if score.composite >= b.lower)
    eligible = band.max_amount > 0
    return Recommendation(
        app_id=score.app_id,
        eligible=eligible,
        product=band.product,
        amount=band.max_amount,
        indicative_rate=band.indicative_rate,
        tenor_months=band.max_tenor_months,
        band_floor=band.lower,
        out_of_policy=False,
        policy_clause_refs=[],
    )
