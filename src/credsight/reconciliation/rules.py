"""Deterministic reconciliation + fraud rules. Each rule returns a Flag with evidence;
nothing here is an LLM judgement (FR-5/6/8). The LLM later explains these hits, never
creates them.

Tolerances are config so they can be calibrated and audited."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..data.schema import CanonicalProfile


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    FRAUD = "fraud"


@dataclass(frozen=True)
class Flag:
    code: str
    severity: Severity
    message: str
    evidence: dict = field(default_factory=dict)


# --- Tolerances (calibrate against synthetic data; document changes) ---
GST_BANK_TURNOVER_TOLERANCE = 0.30  # >30% gap between GST turnover and bank inflows -> WARN
CIRCULAR_UPI_SELF_RATIO = 0.25  # >25% UPI value cycling among few related payers -> FRAUD signal
PRE_APP_INFLOW_SPIKE = 3.0  # last-month inflow > 3x trailing average -> FRAUD signal


def gst_vs_bank_turnover(cp: CanonicalProfile) -> Flag | None:
    """GST-declared turnover vs bank inflows beyond tolerance lowers confidence + flags."""
    gst_total = sum(r.turnover for r in cp.gst_returns)
    bank_inflows = sum(t.amount for a in cp.accounts for t in a.txns if t.amount > 0)
    if gst_total <= 0 or bank_inflows <= 0:
        return None
    gap = abs(gst_total - bank_inflows) / max(gst_total, bank_inflows)
    if gap > GST_BANK_TURNOVER_TOLERANCE:
        return Flag(
            code="GST_BANK_GAP",
            severity=Severity.WARN,
            message=f"GST vs bank turnover gap {gap:.0%} exceeds tolerance "
            f"{GST_BANK_TURNOVER_TOLERANCE:.0%}.",
            evidence={"gst_total": gst_total, "bank_inflows": bank_inflows, "gap": round(gap, 3)},
        )
    return None


def circular_upi(cp: CanonicalProfile) -> Flag | None:
    """Circular UPI flow among a small set of related payers — a classic gaming pattern.
    Flags when a tiny cluster of payers accounts for an outsized share of inbound value."""
    txns = [t for t in cp.upi_txns if not t.is_reversal]
    if len(txns) < 10:
        return None
    by_payer: dict[str, float] = {}
    for t in txns:
        by_payer[t.payer_vpa or "unknown"] = by_payer.get(t.payer_vpa or "unknown", 0.0) + t.amount
    total = sum(by_payer.values())
    if total <= 0:
        return None
    top3 = sum(sorted(by_payer.values(), reverse=True)[:3])
    concentration = top3 / total
    reversal_rate = sum(1 for t in cp.upi_txns if t.is_reversal) / max(len(cp.upi_txns), 1)
    # Few distinct payers carrying most value + high reversals = circular gaming.
    if len(by_payer) <= 5 and concentration > (1 - CIRCULAR_UPI_SELF_RATIO):
        return Flag(
            code="CIRCULAR_UPI",
            severity=Severity.FRAUD,
            message=f"UPI value concentrated in {len(by_payer)} payers "
            f"({concentration:.0%} via top 3); reversal rate {reversal_rate:.0%}.",
            evidence={"distinct_payers": len(by_payer),
                      "top3_concentration": round(concentration, 3),
                      "reversal_rate": round(reversal_rate, 3)},
        )
    return None


def pre_application_inflow_spike(cp: CanonicalProfile) -> Flag | None:
    """Anomalous inflow spike right before application — inflating apparent cash-flow.
    Flags when the final month's bank inflow exceeds the trailing average by PRE_APP_INFLOW_SPIKE."""
    from collections import defaultdict

    by_month: dict[str, float] = defaultdict(float)
    for a in cp.accounts:
        for t in a.txns:
            if t.amount > 0 and not t.is_bounce:
                by_month[f"{t.txn_date.year}-{t.txn_date.month:02d}"] += t.amount
    if len(by_month) < 4:
        return None
    months = [by_month[k] for k in sorted(by_month)]
    last, trailing = months[-1], months[:-1]
    avg = sum(trailing) / len(trailing)
    if avg > 0 and last > avg * PRE_APP_INFLOW_SPIKE:
        return Flag(
            code="INFLOW_SPIKE",
            severity=Severity.FRAUD,
            message=f"Final-month inflow {last:,.0f} is {last / avg:.1f}x the trailing "
            f"average {avg:,.0f} — possible pre-application inflation.",
            evidence={"last_month": round(last, 2), "trailing_avg": round(avg, 2),
                      "ratio": round(last / avg, 2)},
        )
    return None


ALL_RULES = [gst_vs_bank_turnover, circular_upi, pre_application_inflow_spike]


def run_rules(cp: CanonicalProfile) -> list[Flag]:
    return [flag for rule in ALL_RULES if (flag := rule(cp)) is not None]
