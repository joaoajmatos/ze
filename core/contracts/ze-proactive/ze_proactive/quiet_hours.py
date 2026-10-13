from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import asyncpg

from ze_logging import get_logger
from ze_proactive.types import QuietHoursSetting

log = get_logger(__name__)

_COLUMNS = "quiet_hours_enabled, quiet_start, quiet_end, timezone, updated_at"


def is_active(setting: QuietHoursSetting, now_utc: datetime) -> bool:
    if (
        not setting.enabled
        or setting.start is None
        or setting.end is None
        or setting.timezone is None
    ):
        return False
    local = now_utc.astimezone(ZoneInfo(setting.timezone)).time()
    if setting.start < setting.end:
        return setting.start <= local < setting.end
    return local >= setting.start or local < setting.end


def _to_setting(row: asyncpg.Record | None) -> QuietHoursSetting:
    if row is None:
        return QuietHoursSetting(False, None, None, None, None)
    return QuietHoursSetting(
        enabled=row["quiet_hours_enabled"],
        start=row["quiet_start"],
        end=row["quiet_end"],
        timezone=row["timezone"],
        updated_at=row["updated_at"],
    )


class InterruptionSettingsStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get(self) -> QuietHoursSetting:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM interruption_settings WHERE id"
            )
        return _to_setting(row)

    async def upsert(
        self, enabled: bool, start: time | None, end: time | None, timezone: str | None
    ) -> QuietHoursSetting:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                INSERT INTO interruption_settings
                    (id, quiet_hours_enabled, quiet_start, quiet_end, timezone, updated_at)
                VALUES (TRUE, $1, $2, $3, $4, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    quiet_hours_enabled = EXCLUDED.quiet_hours_enabled,
                    quiet_start = EXCLUDED.quiet_start,
                    quiet_end = EXCLUDED.quiet_end,
                    timezone = EXCLUDED.timezone,
                    updated_at = NOW()
                RETURNING {_COLUMNS}
                """,
                enabled,
                start,
                end,
                timezone,
            )
        log.info("quiet_hours_updated", enabled=enabled)
        return _to_setting(row)
