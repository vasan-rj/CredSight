"""Tool functions the orchestrator graph (and, later, the MCP servers + deepagents
subagents) call. Each wraps a real service so the agent layer never re-implements logic.
These are the typed seams that the MCP tool contracts (ref-doc 05) bind to.

Ingestion here uses the synthetic generator path; flipping to a sandbox connector
(connectors.get_connector) is a config change, not a code change."""

from __future__ import annotations

from ..data.generators.archetypes import Archetype
from ..data.generators.generate import generate_bundle
from ..data.ingest import build_canonical
from ..data.schema import CanonicalProfile
from ..reconciliation.reconcile import reconcile
from ..reconciliation.rules import Flag
from ..scoring.model import predict
from ..scoring.policy import Recommendation, recommend
from ..scoring.schema import FeatureVector, ScoreResult


def tool_ingest(app_id: str, archetype: str, seed: int, name: str = "MSME") -> CanonicalProfile:
    """Consent + ingestion: pull and normalise the MSME's alternate data (synthetic)."""
    bundle = generate_bundle(app_id, name, Archetype(archetype), seed)
    return build_canonical(app_id, bundle)


def tool_reconcile(cp: CanonicalProfile) -> tuple[FeatureVector, list[Flag]]:
    """Reconcile + enrich: cross-source checks, fraud flags, feature derivation."""
    return reconcile(cp)


def tool_score(fv: FeatureVector) -> ScoreResult:
    """Deterministic, versioned scoring (the LLM never enters here)."""
    return predict(fv)


def tool_recommend(score: ScoreResult) -> Recommendation:
    """Policy-checked recommendation (always a recommendation, never an executed action)."""
    return recommend(score)


def tool_action_create_offer(app_id: str, rec: Recommendation) -> dict:
    """Post-approval action: generate the OCEN/ULI offer (idempotent by app_id).

    Stub returns the offer payload; the real OCEN/LOS MCP tools wire in on sandbox access.
    The idempotency key prevents double-booking (FR-20)."""
    return {
        "offer_id": f"OFFER-{app_id}",
        "idempotency_key": app_id,
        "amount": rec.amount,
        "rate": rec.indicative_rate,
        "tenor_months": rec.tenor_months,
        "product": rec.product,
    }
