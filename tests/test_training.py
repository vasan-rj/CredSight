"""Trained-model path: train a tiny calibrated XGBoost into a tmp dir and exercise the
real SHAP explanation. Kept small + isolated (tmp base) so it doesn't touch the real
artifact or slow the suite."""

from __future__ import annotations

import pytest

pytest.importorskip("xgboost")
pytest.importorskip("sklearn")

from credsight.data.generators.archetypes import Archetype  # noqa: E402
from credsight.data.generators.generate import generate_bundle  # noqa: E402
from credsight.data.ingest import build_canonical  # noqa: E402
from credsight.governance.faithfulness import is_faithful, safe_template  # noqa: E402
from credsight.reconciliation.reconcile import reconcile  # noqa: E402
from credsight.scoring import artifacts, explain, train  # noqa: E402
from credsight.scoring.features import FEATURE_ORDER  # noqa: E402
from credsight.scoring.schema import SCORE_MAX, SCORE_MIN  # noqa: E402


def _fv(arch: Archetype, seed: int = 5):
    b = generate_bundle("X", "x", arch, seed)
    cp = build_canonical("X", b)
    fv, _ = reconcile(cp)
    return fv


def test_train_save_load_and_explain(tmp_path):
    metrics = train.train(n_per_archetype=30, seed=3, base=tmp_path)
    assert metrics["n_samples"] == 30 * len(list(Archetype))
    assert 0.0 <= metrics["test_auc"] <= 1.0
    assert 0.0 < metrics["positive_rate"] < 1.0  # non-degenerate labels

    tm = artifacts.load("v0", base=tmp_path)
    assert tm is not None
    assert tm.feature_order == FEATURE_ORDER

    composite, drivers = explain.predict_and_explain(tm, _fv(Archetype.STRONG))
    assert SCORE_MIN <= composite <= SCORE_MAX
    assert drivers, "expected SHAP drivers"
    assert all(d.feature in FEATURE_ORDER for d in drivers)
    # Drivers sorted by importance.
    mags = [abs(d.shap_value) for d in drivers]
    assert mags == sorted(mags, reverse=True)


def test_trained_model_ranks_strong_over_stressed(tmp_path):
    train.train(n_per_archetype=40, seed=9, base=tmp_path)
    tm = artifacts.load("v0", base=tmp_path)
    strong, _ = explain.predict_and_explain(tm, _fv(Archetype.STRONG))
    stressed, _ = explain.predict_and_explain(tm, _fv(Archetype.STRESSED))
    assert strong > stressed


def test_explanation_template_is_faithful_to_real_drivers(tmp_path):
    train.train(n_per_archetype=30, seed=3, base=tmp_path)
    tm = artifacts.load("v0", base=tmp_path)
    _, drivers = explain.predict_and_explain(tm, _fv(Archetype.THIN_FILE))
    text = safe_template(drivers)
    assert is_faithful(text, drivers, clause_refs=[])
