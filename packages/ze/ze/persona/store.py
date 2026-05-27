from __future__ import annotations

import asyncpg

from ze.logging import get_logger
from ze.persona.types import PersonaState
from ze.settings import Settings

log = get_logger(__name__)

_KNOWN_DIALS = {"humor", "directness", "formality", "depth"}


class PersonaStore:
    def __init__(self, pool: asyncpg.Pool, settings: Settings) -> None:
        self._pool = pool
        self._settings = settings

    # ── Public ────────────────────────────────────────────────────────────────

    async def get_active(self) -> dict:
        """Return the active profile dict with DB dial overrides merged in."""
        state = await self._load_state()
        profile = self._resolve_profile(state.profile)
        if state.dials:
            merged_dials = {**profile.get("dials", {}), **state.dials}
            return {**profile, "dials": merged_dials}
        return profile

    async def get_state(self) -> PersonaState:
        """Return the raw DB state (profile name + dial overrides)."""
        return await self._load_state()

    async def set_profile(self, name: str) -> None:
        """Switch to a named profile and clear dial overrides."""
        if name not in self.available_profiles():
            raise ValueError(f"Unknown profile {name!r}. Available: {self.available_profiles()}")
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE persona_state SET profile = $1, dials = '{}', updated_at = NOW() WHERE id = 1",
                name,
            )
        log.info("persona_profile_set", profile=name)

    async def set_dial(self, name: str, value: float) -> None:
        """Override one dial on the current profile."""
        if name not in _KNOWN_DIALS:
            raise ValueError(f"Unknown dial {name!r}. Known dials: {sorted(_KNOWN_DIALS)}")
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"Dial value must be in [0.0, 1.0], got {value}")
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE persona_state
                SET dials = dials || jsonb_build_object($1::text, $2::float),
                    updated_at = NOW()
                WHERE id = 1
                """,
                name,
                value,
            )
        log.info("persona_dial_set", dial=name, value=value)

    async def reset_dials(self) -> None:
        """Restore all dials to the active profile's YAML defaults."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE persona_state SET dials = '{}', updated_at = NOW() WHERE id = 1"
            )
        log.info("persona_dials_reset")

    def available_profiles(self) -> list[str]:
        """Names of all profiles defined in YAML config."""
        profiles = self._settings.persona_config.get("profiles", {})
        return list(profiles.keys()) if profiles else ["default"]

    # ── Private ───────────────────────────────────────────────────────────────

    async def _load_state(self) -> PersonaState:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT profile, dials, updated_at FROM persona_state WHERE id = 1"
            )
        if row is None:
            # Table exists but seed INSERT hasn't run (shouldn't happen post-migration).
            return PersonaState(profile=self._yaml_default_profile_name())
        return PersonaState(
            profile=row["profile"],
            dials=dict(row["dials"] or {}),
            updated_at=row["updated_at"],
        )

    def _resolve_profile(self, name: str) -> dict:
        """Return the profile dict for the given name, falling back to the first profile."""
        profiles = self._settings.persona_config.get("profiles", {})
        if profiles:
            return dict(profiles.get(name) or next(iter(profiles.values())))
        # Legacy flat format.
        cfg = self._settings.persona_config
        return {
            "traits": cfg.get("traits", ["direct", "warm", "concise"]),
            "verbosity": cfg.get("verbosity", "concise"),
            "custom_instructions": cfg.get("custom_instructions", ""),
            "dials": {},
        }

    def _yaml_default_profile_name(self) -> str:
        return self._settings.persona_config.get("profile", "default")
