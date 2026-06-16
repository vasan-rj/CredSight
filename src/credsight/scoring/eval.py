"""Evaluation harness — run in CI from day one (ref-doc 04 §Evaluation harness).

Measures:
  - Decision quality: AUC/KS ranking + calibration error vs synthetic ground-truth labels.
  - Explanation faithfulness: % of explanations whose cited drivers match the model's
    actual top SHAP features (target ~100%).
  - Stability: small input perturbations must not swing the band.

Three fixed regression archetypes (thin-file, strong, stressed) are re-run on every change.
"""

from __future__ import annotations

import sys

from ..data.generators.archetypes import Archetype
from ..data.generators.generate import generate_bundle
from ..data.ingest import build_canonical
from ..reconciliation.reconcile import reconcile
from .model import predict

# Fixed regression archetypes (ref-doc 04). Expected composite ordering: strong > thin >
# stressed; fraud should be caught by reconciliation, not trusted by score alone.
_REGRESSION = [Archetype.THIN_FILE, Archetype.STRONG, Archetype.STRESSED, Archetype.FRAUD]


def _score_archetype(arch: Archetype, seed: int):
    bundle = generate_bundle(f"EVAL-{arch.value}", f"Eval {arch.value}", arch, seed)
    cp = build_canonical(bundle["msme_id"], bundle)
    fv, flags = reconcile(cp)
    return predict(fv), flags


def evaluate() -> dict:
    """Score the fixed regression archetypes and report ranking + stability sanity checks.

    Until a trained, labelled model exists, this reports the deterministic-core invariants
    that must hold on every change (composite ordering, fraud detection, band stability).
    AUC/KS/calibration land once the trained XGBoost + labelled synthetic set exist."""
    results = {a: _score_archetype(a, seed=900 + i) for i, a in enumerate(_REGRESSION)}
    composites = {a.value: r[0].composite for a, r in results.items()}

    strong = composites["strong"]
    stressed = composites["stressed"]
    fraud_flags = [f.code for f in results[Archetype.FRAUD][1] if f.severity.value == "fraud"]

    # Band stability: re-score strong with a different seed; band should not jump.
    strong_alt, _ = _score_archetype(Archetype.STRONG, seed=12345)
    stability = abs(strong - strong_alt.composite)

    return {
        "composites": composites,
        "ranking_ok": strong > stressed,
        "fraud_detected": fraud_flags,
        "strong_band_stability_delta": stability,
        # Filled when a trained, labelled model exists:
        "auc": None, "ks": None, "calibration_error": None,
        "explanation_faithfulness": None,
    }


def main() -> int:
    metrics = evaluate()
    for k, v in metrics.items():
        print(f"{k:28s}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
