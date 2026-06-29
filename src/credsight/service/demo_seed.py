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
    sector: str = ""  # overrides archetype-default if set


# Named demo applicants — fixed seeds for reproducibility. Original 4 + 16 expanded catalog.
DEMO: list[DemoApplicant] = [
    # ── Original golden-demo archetypes ──────────────────────────────────────
    DemoApplicant("APP-LAKSHMI-001", "Lakshmi Stores",    Archetype.THIN_FILE, seed=101, sector="Kirana / retail"),
    DemoApplicant("MSME0002",        "Sri Auto Works",    Archetype.STRONG,    seed=102, sector="Micro-manufacturing"),
    DemoApplicant("MSME0005",        "Anand Tailors",     Archetype.STRESSED,  seed=103, sector="Services"),
    DemoApplicant("MSME0007",        "Deccan Traders",    Archetype.FRAUD,     seed=104, sector="Wholesale"),

    # ── Thin-file / NTC expansion (seed 201-205) ──────────────────────────────
    DemoApplicant("MSME0201", "Priya Flower Vendor",    Archetype.THIN_FILE, seed=201, sector="Street vendor / flowers"),
    DemoApplicant("MSME0202", "Ramesh Cobblers",        Archetype.THIN_FILE, seed=202, sector="Repair services"),
    DemoApplicant("MSME0203", "Fatima Street Food",     Archetype.THIN_FILE, seed=203, sector="Food & beverages"),
    DemoApplicant("MSME0204", "Suresh Pan Shop",        Archetype.THIN_FILE, seed=204, sector="Kirana / retail"),
    DemoApplicant("MSME0205", "Gita Tailoring Unit",    Archetype.THIN_FILE, seed=205, sector="Textile / apparel"),

    # ── Strong / growth archetype expansion (seed 206-209) ───────────────────
    DemoApplicant("MSME0206", "Raj Pharma Retail",      Archetype.STRONG,    seed=206, sector="Healthcare"),
    DemoApplicant("MSME0207", "Meera IT Services",      Archetype.STRONG,    seed=207, sector="IT services"),
    DemoApplicant("MSME0208", "Kumar Auto Dealer",      Archetype.STRONG,    seed=208, sector="Auto repair / parts"),
    DemoApplicant("MSME0209", "Sathya Dairy Farm",      Archetype.STRONG,    seed=209, sector="Agriculture / dairy"),

    # ── Stressed / declining archetype expansion (seed 210-213) ──────────────
    DemoApplicant("MSME0210", "Mohan Restaurant",       Archetype.STRESSED,  seed=210, sector="Food & beverages"),
    DemoApplicant("MSME0211", "Kavitha Textiles",       Archetype.STRESSED,  seed=211, sector="Textile / apparel"),
    DemoApplicant("MSME0212", "Ravi Construction",      Archetype.STRESSED,  seed=212, sector="Construction"),
    DemoApplicant("MSME0213", "Sunita Handicrafts",     Archetype.STRESSED,  seed=213, sector="Handicrafts"),

    # ── Fraud signal variants (seed 214-216) ─────────────────────────────────
    DemoApplicant("MSME0214", "Vijay Used Goods",       Archetype.FRAUD,     seed=214, sector="Wholesale"),
    DemoApplicant("MSME0215", "Arjun Cash Wholesale",   Archetype.FRAUD,     seed=215, sector="Wholesale"),
    DemoApplicant("MSME0216", "Nanda Import Agents",    Archetype.FRAUD,     seed=216, sector="Wholesale"),
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
