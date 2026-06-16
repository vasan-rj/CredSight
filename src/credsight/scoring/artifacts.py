"""Trained-model artifact: the XGBoost classifier + its probability calibrator + the
feature order it was trained on, persisted together so scoring is reproducible and the
column order can never drift from the model.

Artifacts are NOT committed (regenerate via `credsight-train`); the path is gitignored."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

ARTIFACT_DIR = Path(__file__).parent / "artifacts"


@dataclass
class TrainedModel:
    clf: Any            # xgboost.XGBClassifier
    calibrator: Any     # sklearn IsotonicRegression mapping raw P(bad) -> calibrated
    feature_order: list[str]
    version: str


def path(version: str, base: Path | None = None) -> Path:
    return (base or ARTIFACT_DIR) / f"composite_{version}.joblib"


def save(tm: TrainedModel, base: Path | None = None) -> Path:
    import joblib

    p = path(tm.version, base)
    p.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(tm, p)
    return p


_CACHE: dict[str, tuple[float, TrainedModel]] = {}


def load(version: str, base: Path | None = None) -> TrainedModel | None:
    """Load (and cache by path+mtime) the trained model, or None if not yet trained."""
    p = path(version, base)
    if not p.exists():
        return None
    key, mtime = str(p), p.stat().st_mtime
    cached = _CACHE.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    import joblib

    tm = joblib.load(p)
    _CACHE[key] = (mtime, tm)
    return tm
