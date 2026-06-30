"""IDBI MSME product catalogue + needs-based matcher.

Products are defined once here; `match_products()` filters and ranks them against the
NeedsAssessment (and optionally a ScoreResult) so the UI can show the right 2-3 products.

Crucially, several products need NO credit score — they're needs-based or invoice-backed.
That's the consent-free entry story: GST alone → identify need → show a relevant product
→ invite AA consent for the full score-backed offer."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel

from .classifier import NeedsAssessment

# ScoreResult is only imported if actually passed — keep the import lazy to
# avoid circular deps and to emphasise that scoring is optional here.


# ── product catalogue ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Product:
    id: str
    name: str
    tagline: str
    description: str
    serves_needs: list[str]      # need_type values this product addresses
    min_score_band: int | None   # None = no score required (needs-based entry)
    amount_min: int
    amount_max: int
    tenor_min: int               # months
    tenor_max: int
    indicative_rate: float       # annual %
    key_features: list[str]
    data_needed: list[str]       # "gst" | "bank_aa" | "upi" | "bureau"


CATALOGUE: list[Product] = [
    Product(
        id="wc_unsecured",
        name="MSME Working Capital Limit",
        tagline="Keep your business running without interruption",
        description="Revolving unsecured credit line for day-to-day working capital needs. "
                    "Sized to your GST turnover and bank cash-flow.",
        serves_needs=["working_capital"],
        min_score_band=600,
        amount_min=100_000, amount_max=2_500_000,
        tenor_min=12, tenor_max=36,
        indicative_rate=18.0,
        key_features=["No collateral required", "Revolving facility", "Disburse in 48h"],
        data_needed=["gst", "bank_aa"],
    ),
    Product(
        id="seasonal_credit",
        name="Seasonal Credit Line",
        tagline="Stock up before the season, pay back after",
        description="Short-duration credit line designed for seasonal inventory cycles — "
                    "festivals, harvest, garment season. No long-term EMI commitment.",
        serves_needs=["seasonal", "working_capital"],
        min_score_band=None,   # needs-based, score optional
        amount_min=50_000, amount_max=1_000_000,
        tenor_min=3, tenor_max=6,
        indicative_rate=22.0,
        key_features=["90–180 day tenor", "GST + UPI entry", "No collateral"],
        data_needed=["gst", "upi"],
    ),
    Product(
        id="gst_scf",
        name="GST Supply Chain Finance",
        tagline="Turn your GST invoices into immediate cash",
        description="Invoice-backed financing against GST-verified B2B invoices. "
                    "No full credit scoring required — GST data alone is enough to begin.",
        serves_needs=["trade_finance", "working_capital"],
        min_score_band=None,   # invoice-backed
        amount_min=100_000, amount_max=2_500_000,
        tenor_min=1, tenor_max=6,
        indicative_rate=20.0,
        key_features=["GST-data entry — no AA needed", "Invoice-backed, no fixed EMI",
                      "Revolving as invoices are raised"],
        data_needed=["gst"],
    ),
    Product(
        id="term_loan",
        name="MSME Term Loan",
        tagline="Invest in your business's next chapter",
        description="Structured term loan for equipment, infrastructure, or business expansion. "
                    "Fixed EMI with longer tenors for established enterprises.",
        serves_needs=["capex"],
        min_score_band=680,
        amount_min=500_000, amount_max=10_000_000,
        tenor_min=12, tenor_max=84,
        indicative_rate=16.0,
        key_features=["Fixed EMI", "Up to 7-year tenor", "Equipment / expansion"],
        data_needed=["gst", "bank_aa"],
    ),
    Product(
        id="ntc_starter",
        name="NTC Starter Credit",
        tagline="Your first step into formal credit",
        description="Entry credit facility for New-to-Credit micro-enterprises with no prior "
                    "borrowing history. GST + UPI activity is sufficient to qualify.",
        serves_needs=["working_capital"],
        min_score_band=None,   # NTC — no prior credit required
        amount_min=25_000, amount_max=200_000,
        tenor_min=6, tenor_max=18,
        indicative_rate=24.0,
        key_features=["No credit history needed", "GST + UPI based", "Builds your credit profile"],
        data_needed=["gst", "upi"],
    ),
]

_PRODUCT_BY_ID: dict[str, Product] = {p.id: p for p in CATALOGUE}


# ── match output ──────────────────────────────────────────────────────────────

class ProductMatch(BaseModel):
    product_id: str
    name: str
    tagline: str
    description: str
    amount_estimate: int
    tenor_range: list[int]       # [min, max] — list for JSON serialisation
    indicative_rate: float
    key_features: list[str]
    fit_reason: str
    data_needed: list[str]
    score_required: bool
    score_band_ok: bool          # True when no score required or current score qualifies


# ── matcher ───────────────────────────────────────────────────────────────────

def match_products(
    assessment: NeedsAssessment,
    score=None,                  # ScoreResult | None — optional, type-checked lazily
    max_products: int = 3,
) -> list[ProductMatch]:
    """Rank and return up to `max_products` products that fit the assessed need.

    Works with or without a score. When `score` is absent (consent-free stage), products
    with no score gate are prioritised so the MSME sees actionable offers immediately."""
    composite = score.composite if score is not None else None

    matches: list[ProductMatch] = []
    for p in CATALOGUE:
        # needs match: primary OR this product also serves working_capital (broad fallback)
        primary_match = assessment.need_type in p.serves_needs
        secondary_match = "working_capital" in p.serves_needs and assessment.need_type == "working_capital"
        if not (primary_match or secondary_match):
            continue

        # NTC filter: only offer ntc_starter to genuine thin-file/NTC cases
        if p.id == "ntc_starter" and assessment.estimated_amount > 200_000:
            continue  # too large for the starter product
        if p.id == "ntc_starter" and assessment.need_type not in ("working_capital",):
            continue

        # score gate
        band_ok = True
        if p.min_score_band is not None and composite is not None:
            band_ok = composite >= p.min_score_band

        # size estimate: clamp to product range
        amount = max(p.amount_min, min(assessment.estimated_amount, p.amount_max))

        # fit reason
        if not band_ok:
            fit_reason = f"Available once score reaches band {p.min_score_band} — raise your score first"
        elif assessment.need_type == "seasonal" and "seasonal" in p.serves_needs:
            fit_reason = "Designed for seasonal inventory cycles"
        elif assessment.need_type == "trade_finance" and "trade_finance" in p.serves_needs:
            fit_reason = "Invoice-backed — GST data alone is enough to start"
        elif assessment.need_type == "capex" and "capex" in p.serves_needs:
            fit_reason = "Structured for equipment and expansion"
        elif p.id == "ntc_starter":
            fit_reason = "Built for first-time borrowers — no credit history needed"
        elif p.id == "gst_scf":
            fit_reason = "No AA consent required — GST invoices are the collateral"
        else:
            fit_reason = "Fits your estimated working capital gap"

        matches.append(ProductMatch(
            product_id=p.id,
            name=p.name,
            tagline=p.tagline,
            description=p.description,
            amount_estimate=amount,
            tenor_range=[p.tenor_min, p.tenor_max],
            indicative_rate=p.indicative_rate,
            key_features=p.key_features,
            fit_reason=fit_reason,
            data_needed=p.data_needed,
            score_required=p.min_score_band is not None,
            score_band_ok=band_ok,
        ))

    # Sort: eligible first (band_ok), then by estimated amount desc
    matches.sort(key=lambda m: (not m.score_band_ok, -m.amount_estimate))
    return matches[:max_products]
