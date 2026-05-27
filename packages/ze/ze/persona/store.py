"""Ze wiring for ze-core PostgresPersonaStore (profiles from persona.yaml)."""

from __future__ import annotations

from ze.settings import Settings
from ze_core.persona.postgres import PostgresPersonaStore


class PersonaStore(PostgresPersonaStore):
    """Postgres persona store with profiles loaded from settings.persona_config."""

    def __init__(self, pool, settings: Settings) -> None:
        cfg = settings.persona_config
        super().__init__(
            pool=pool,
            profiles=cfg.get("profiles", {}),
            default_profile=cfg.get("profile", "default"),
        )
