"""In-memory application store for the demo/challenge. Swap for Postgres (PRD §8) by
keeping this interface. Seeds the demo applicants on first access so the API + frontend
have real, model-computed data without a separate setup step."""

from __future__ import annotations

from .demo_seed import all_seeds
from .models import Application
from .pipeline import assess


class ApplicationStore:
    def __init__(self) -> None:
        self._apps: dict[str, Application] = {}
        self._seeded = False

    def _ensure_seeded(self) -> None:
        if self._seeded:
            return
        for s in all_seeds():
            self._apps[s.fv.app_id] = assess(
                s.fv, name=s.name, sector=s.sector, consent_ref=s.consent_ref,
                flags=s.flags,
            )
        self._seeded = True

    def get(self, app_id: str) -> Application | None:
        self._ensure_seeded()
        return self._apps.get(app_id)

    def all(self) -> list[Application]:
        self._ensure_seeded()
        return list(self._apps.values())

    def put(self, app: Application) -> None:
        self._apps[app.app_id] = app


store = ApplicationStore()
