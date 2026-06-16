"""Demo applicants, now driven by the REAL chain: generate a coherent bundle ->
ingest to canonical -> reconcile to features + flags. The API/portfolio thus show scores
computed by the deterministic model over data produced by the synthetic generators and
the reconciliation feature pipeline — no hardcoded numbers anywhere.

Lakshmi is the golden-demo MSME. Deccan is the fraud archetype, so the reconciliation
fraud flags fire live (the memorable demo beat)."""

from __future__ import annotations

from dataclasses import dataclass

from ..data.generators.archetypes import Archetype
from ..data.generators.generate import generate_bundle
from ..data.ingest import build_canonical
from ..reconciliation.reconcile import reconcile
from ..reconciliation.rules import Flag
from ..scoring.schema import FeatureVector


@dataclass(frozen=True)
class DemoApplicant:
    app_id: str
    name: str
    archetype: Archetype
    seed: int


# Named demo applicants mapped to archetypes. Fixed seeds -> reproducible demo.
DEMO: list[DemoApplicant] = [
    DemoApplicant("APP-LAKSHMI-001", "Lakshmi Stores", Archetype.THIN_FILE, seed=101),
    DemoApplicant("MSME0002", "Sri Auto Works", Archetype.STRONG, seed=102),
    DemoApplicant("MSME0005", "Anand Tailors", Archetype.STRESSED, seed=103),
    DemoApplicant("MSME0007", "Deccan Traders", Archetype.FRAUD, seed=104),
]


@dataclass(frozen=True)
class SeedResult:
    fv: FeatureVector
    name: str
    sector: str
    consent_ref: str
    flags: list[Flag]


def build(applicant: DemoApplicant) -> SeedResult:
    """Run generate -> ingest -> reconcile for one demo applicant."""
    bundle = generate_bundle(applicant.app_id, applicant.name, applicant.archetype,
                             applicant.seed)
    cp = build_canonical(applicant.app_id, bundle)
    fv, flags = reconcile(cp)
    return SeedResult(
        fv=fv, name=applicant.name, sector=cp.profile.sector or "—",
        consent_ref=cp.consent.consent_id, flags=flags,
    )


def all_seeds() -> list[SeedResult]:
    return [build(a) for a in DEMO]
