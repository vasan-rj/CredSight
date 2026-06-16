"""Reconciliation entrypoint: canonical profile -> feature vector + flags.

Derives the model's feature vector (the 12 features scoring/dimensions.py reads) and the
thin-file confidence inputs (n_sources, months_history, cross_source_agreement) from the
canonical data. Pure, deterministic — the LLM never derives features."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date

from ..data.schema import BankAccount, CanonicalProfile, SourceKind
from ..scoring.schema import FeatureVector
from .rules import Flag, run_rules


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _all_bank_txns(accounts: list[BankAccount]):
    return [t for a in accounts for t in a.txns]


def _monthly_inflows(accounts: list[BankAccount]) -> list[float]:
    by_month: dict[str, float] = defaultdict(float)
    for t in _all_bank_txns(accounts):
        if t.amount > 0 and not t.is_bounce:
            by_month[f"{t.txn_date.year}-{t.txn_date.month:02d}"] += t.amount
    return [by_month[k] for k in sorted(by_month)]


def _cv(values: list[float]) -> float:
    """Coefficient of variation (stdev/mean). 0 when <2 points or mean 0."""
    if len(values) < 2:
        return 0.0
    mean = statistics.fmean(values)
    if mean == 0:
        return 0.0
    return statistics.pstdev(values) / mean


def _reference_date(cp: CanonicalProfile) -> date:
    """Latest data date — used as 'now' for vintage so it stays deterministic."""
    dates = [t.txn_date for t in _all_bank_txns(cp.accounts)]
    if dates:
        return max(dates)
    if cp.gst_returns:
        y, m = (int(x) for x in max(r.period for r in cp.gst_returns).split("-"))
        return date(y, m, 1)
    return date(2026, 6, 1)


# ---------------------------------------------------------------------------
# Feature derivation (ref-doc 04 §Feature examples)
# ---------------------------------------------------------------------------

def _bank_features(cp: CanonicalProfile, feats: dict) -> None:
    txns = _all_bank_txns(cp.accounts)
    if not txns:
        return
    inflows = _monthly_inflows(cp.accounts)
    total_in = sum(t.amount for t in txns if t.amount > 0 and not t.is_bounce)
    total_out = sum(-t.amount for t in txns if t.amount < 0)
    n_months = max(len(inflows), 1)

    feats["inflow_regularity"] = _clamp(1.0 - _cv(inflows))
    feats["inflow_outflow_ratio"] = (total_in / total_out) if total_out > 0 else 1.0

    balances = [t.balance_after for t in txns if t.balance_after is not None]
    if len(balances) >= 2:
        mean_bal = statistics.fmean(balances)
        vol = (statistics.pstdev(balances) / mean_bal) if mean_bal > 0 else 1.0
        feats["balance_volatility_norm"] = _clamp(vol)

    bounces = sum(1 for t in txns if t.is_bounce)
    feats["bounce_rate"] = _clamp(bounces / n_months)

    obligations = [t for t in txns if t.is_obligation and not t.is_bounce]
    bounced_obl = sum(1 for t in txns if t.is_obligation and t.is_bounce)
    feats["obligation_servicing_ratio"] = _clamp(
        1.0 - (bounced_obl / max(len(obligations), 1))
    )
    emi_total = sum(-t.amount for t in obligations if t.amount < 0)
    feats["emi_to_inflow_ratio"] = _clamp(emi_total / total_in) if total_in > 0 else 0.0


def _gst_features(cp: CanonicalProfile, feats: dict, ref: date, window_months: int) -> None:
    returns = cp.gst_returns
    if returns:
        feats["gst_filing_punctuality"] = sum(r.filed_on_time for r in returns) / len(returns)
        turnovers = [r.turnover for r in returns]  # ordered oldest->newest by generation
        k = max(1, len(turnovers) // 3)
        first, last = turnovers[:k], turnovers[-k:]
        mean_first = statistics.fmean(first) if first else 0.0
        feats["gst_turnover_trend"] = (
            (statistics.fmean(last) / mean_first - 1.0) if mean_first > 0 else 0.0
        )
        # Continuity: returns filed vs months in the observation window (not the full
        # registration age — an old business with a short data window is still continuous).
        continuity = _clamp(len(returns) / max(window_months, 1))
        feats["gst_filing_continuity"] = continuity
        feats["operational_stability"] = continuity  # proxy until address-stability data

    # Vintage from registration date.
    if cp.profile.gst_registration_date:
        months_registered = max(
            1, (ref.year - cp.profile.gst_registration_date.year) * 12
            + (ref.month - cp.profile.gst_registration_date.month)
        )
        feats["gst_vintage_years"] = months_registered / 12.0


def _other_features(cp: CanonicalProfile, feats: dict) -> None:
    if cp.epfo:
        feats["epfo_formality_proxy"] = _clamp(cp.epfo.active_employees / 10.0)
    else:
        feats["epfo_formality_proxy"] = 0.0


def _cross_source_agreement(cp: CanonicalProfile) -> float:
    """1.0 = GST turnover and bank inflows agree; lower as they diverge (the fraud signal
    that also dampens confidence). Compares declared GST turnover vs observed bank inflow."""
    gst_total = sum(r.turnover for r in cp.gst_returns)
    bank_total = sum(t.amount for a in cp.accounts for t in a.txns
                     if t.amount > 0 and not t.is_bounce)
    if gst_total <= 0 or bank_total <= 0:
        return 0.8  # only one side present -> mild penalty, not a contradiction
    gap = abs(gst_total - bank_total) / max(gst_total, bank_total)
    return round(_clamp(1.0 - gap), 3)


def derive_features(cp: CanonicalProfile) -> FeatureVector:
    """Turn the canonical profile into the model's feature vector."""
    ref = _reference_date(cp)
    present = {SourceKind.BANK_AA, SourceKind.GST, SourceKind.UPI, SourceKind.EPFO,
               SourceKind.BUREAU} - set(cp.missing_sources)
    months = len({f"{t.txn_date.year}-{t.txn_date.month:02d}"
                  for a in cp.accounts for t in a.txns}) or len(cp.gst_returns)

    feats: dict[str, float] = {}
    _bank_features(cp, feats)
    _gst_features(cp, feats, ref, window_months=months)
    _other_features(cp, feats)

    return FeatureVector(
        app_id=cp.app_id, features=feats, n_sources=len(present),
        months_history=months, cross_source_agreement=_cross_source_agreement(cp),
    )


def reconcile(cp: CanonicalProfile) -> tuple[FeatureVector, list[Flag]]:
    """Run rules + derive features. Returns (features, flags). Caller persists to the
    virtual filesystem and logs flags with evidence to the audit trail."""
    flags = run_rules(cp)
    fv = derive_features(cp)
    return fv, flags
