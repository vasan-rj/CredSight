"""Explanation faithfulness check (FR-15, ref-doc 04). Generated explanation text may
reference ONLY the model's actual top SHAP drivers and the retrieved policy clauses.
Fails closed to a templated explanation.

This is a programmatic guard, not a vibe check: it runs before any explanation reaches a
human or the audit log, and the eval harness measures faithfulness as a CI metric."""

from __future__ import annotations

from ..scoring.schema import ShapDriver


def allowed_driver_terms(drivers: list[ShapDriver]) -> set[str]:
    """The vocabulary an explanation is permitted to invoke."""
    return {d.feature.lower() for d in drivers}


def is_faithful(explanation: str, drivers: list[ShapDriver], clause_refs: list[str]) -> bool:
    """Check that the explanation references only permitted drivers/clauses.

    TODO(days 11-14): robust check — map driver feature names to their phrasings, verify
    every claimed factor in the explanation traces to a real driver or cited clause.
    Stub: passes when at least the top driver is mentioned; tighten before demo."""
    if not drivers:
        return False
    top = drivers[0].feature.lower().replace("_", " ")
    return top in explanation.lower() or drivers[0].feature.lower() in explanation.lower()


def safe_template(drivers: list[ShapDriver]) -> str:
    """Fallback explanation built purely from the actual drivers — faithful by construction."""
    if not drivers:
        return "Insufficient data to explain this score; routed to a human underwriter."
    parts = []
    for d in drivers[:3]:
        sign = "supports" if d.direction == "positive" else "weakens"
        parts.append(f"{d.feature.replace('_', ' ')} ({sign})")
    return "Key factors: " + "; ".join(parts) + "."
