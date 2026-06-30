"""MSME business-needs classifier (deterministic, no LLM).

Takes a CanonicalProfile (works with GST-only data for the consent-free entry point) and
classifies what kind of financing the business actually needs, estimates a size, and
produces a plain-language headline the bank can show the MSME.

This is the first-half of the journey: identify the need → match a product → *then* invite
full AA consent for precise scoring. Running it at ingest time means the HITL gate and the
underwriter both see the need context alongside the credit decision."""

from __future__ import annotations

import math
from datetime import date

from pydantic import BaseModel

from ..data.schema import CanonicalProfile, SourceKind


# ── output model ────────────────────────────────────────────────────────────────

class NeedsAssessment(BaseModel):
    app_id: str
    need_type: str       # "working_capital" | "seasonal" | "capex" | "trade_finance"
    headline: str        # "Needs ₹2.5L seasonal credit for festive season inventory"
    estimated_amount: int
    urgency: str         # "immediate" | "medium_term" | "planning"
    evidence: list[str]  # bullet chips shown in the UI
    gst_only: bool       # True → derived from GST alone; AA/UPI would improve precision
    consent_to_unlock: list[str]  # human-readable list of what additional data would help


# ── helpers ──────────────────────────────────────────────────────────────────────

def _fmt_amount(n: int) -> str:
    if n >= 100_000:
        return f"{n / 100_000:.1f}".rstrip("0").rstrip(".") + "L"
    return f"{n // 1000}K"


def _annual_turnover(cp: CanonicalProfile) -> float:
    active = [r for r in cp.gst_returns if not r.nil_filing and r.turnover > 0]
    if not active:
        return 0.0
    return sum(r.turnover for r in active) / len(active) * 12


def _vintage_years(reg_date: date | None) -> float:
    if reg_date is None:
        return 0.0
    return (date(2026, 6, 1) - reg_date).days / 365.25  # ANCHOR matches generators


def _is_seasonal(cp: CanonicalProfile) -> bool:
    SEASONAL_SECTORS = {"kirana", "retail", "wholesale", "garment", "textile", "agri"}
    sector = (cp.profile.sector or "").lower()
    if any(s in sector for s in SEASONAL_SECTORS):
        return True
    vals = [r.turnover for r in cp.gst_returns if not r.nil_filing and r.turnover > 0]
    if len(vals) < 4:
        return False
    mean = sum(vals) / len(vals)
    if mean <= 0:
        return False
    std = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
    return std / mean > 0.25


def _turnover_trend(cp: CanonicalProfile) -> float:
    """Positive = growing, negative = declining."""
    active = [r for r in cp.gst_returns if not r.nil_filing and r.turnover > 0]
    if len(active) < 6:
        return 0.0
    recent = sum(r.turnover for r in active[-3:]) / 3
    earlier = sum(r.turnover for r in active[:3]) / 3
    return (recent - earlier) / max(earlier, 1)


def _has_stress(cp: CanonicalProfile) -> bool:
    return any(t.is_bounce for acc in cp.accounts for t in acc.txns)


# ── main classifier ───────────────────────────────────────────────────────────

def classify_needs(cp: CanonicalProfile) -> NeedsAssessment:
    """Classify MSME financing needs from whatever data is available.

    Designed to work with GST-only input (the consent-free entry point) AND with the full
    canonical profile (post-consent). The `gst_only` flag tells the UI whether additional
    consent would improve precision."""
    missing = set(cp.missing_sources)
    gst_only = (
        SourceKind.BANK_AA in missing and
        len(cp.accounts) == 0
    )

    annual = _annual_turnover(cp)
    vintage = _vintage_years(cp.profile.gst_registration_date)
    seasonal = _is_seasonal(cp)
    trend = _turnover_trend(cp)
    stress = _has_stress(cp)
    has_employees = cp.epfo is not None
    is_ntc = vintage < 2.5 or len(cp.gst_returns) < 9
    sector = (cp.profile.sector or "").lower()

    # ── classify ──────────────────────────────────────────────────────────────
    if stress:
        need_type, urgency = "working_capital", "immediate"
    elif "wholesale" in sector or "trade" in sector:
        need_type, urgency = "trade_finance", "medium_term"
    elif seasonal and not has_employees:
        need_type, urgency = "seasonal", "medium_term"
    elif has_employees and vintage > 5 and trend > 0.05:
        need_type, urgency = "capex", "planning"
    else:
        need_type = "working_capital"
        urgency = "immediate" if trend < -0.05 else "medium_term"

    # ── amount estimate ───────────────────────────────────────────────────────
    pcts = {"working_capital": 0.15 if is_ntc else 0.20,
            "seasonal": 0.25, "capex": 0.30, "trade_finance": 0.15}
    raw = int(annual * pcts.get(need_type, 0.20))
    caps = {"ntc": 200_000, "seasonal": 1_000_000, "capex": 5_000_000, "default": 2_500_000}
    cap = caps["ntc"] if is_ntc else caps.get(need_type, caps["default"])
    estimated = max(25_000, min(raw, cap))

    # ── headline ──────────────────────────────────────────────────────────────
    amt_s = f"₹{_fmt_amount(estimated)}"
    if need_type == "seasonal":
        headline = f"Needs {amt_s} seasonal credit for peak-season inventory"
    elif need_type == "capex":
        headline = f"Needs {amt_s} to expand operations or acquire equipment"
    elif need_type == "trade_finance":
        headline = f"Needs {amt_s} supply-chain finance against GST invoices"
    elif is_ntc:
        headline = f"Needs {amt_s} starter credit — first step into formal lending"
    elif stress:
        headline = f"Needs {amt_s} working capital urgently (liquidity stress)"
    else:
        headline = f"Needs {amt_s} working capital to sustain business operations"

    # ── evidence chips ────────────────────────────────────────────────────────
    evidence: list[str] = []
    if annual > 0:
        evidence.append(f"GST turnover ₹{_fmt_amount(int(annual))}/yr")
    if vintage > 0:
        evidence.append(f"{vintage:.1f}yr business vintage")
    if is_ntc:
        evidence.append("New-to-credit (thin file)")
    if seasonal:
        evidence.append("Seasonal revenue pattern")
    if stress:
        evidence.append("Liquidity stress in bank data")
    if trend > 0.05:
        evidence.append(f"Revenue growing +{trend * 100:.0f}%")
    elif trend < -0.05:
        evidence.append(f"Revenue declining {abs(trend) * 100:.0f}%")
    if has_employees:
        evidence.append(f"{cp.epfo.active_employees} EPFO-registered staff")

    # ── consent-to-unlock ─────────────────────────────────────────────────────
    consent_to_unlock: list[str] = []
    if gst_only:
        consent_to_unlock.append("Bank statements (AA) — sharpens scoring precision")
        if SourceKind.UPI in missing:
            consent_to_unlock.append("UPI history — validates daily cash flow")

    return NeedsAssessment(
        app_id=cp.app_id,
        need_type=need_type,
        headline=headline,
        estimated_amount=estimated,
        urgency=urgency,
        evidence=evidence,
        gst_only=gst_only,
        consent_to_unlock=consent_to_unlock,
    )
