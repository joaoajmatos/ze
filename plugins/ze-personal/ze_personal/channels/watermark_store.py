from datetime import datetime, timedelta, timezone

import asyncpg

from ze_logging import get_logger
from ze_personal.channels.types import ChannelPollStatus, PollOutcome


class ChannelWatermarkStore:
    DEFAULT_LOOKBACK_HOURS = 24

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self._log = get_logger(__name__)

    async def get(self, channel_id: str) -> datetime:
        """Return last polled time, or 24 h ago if never polled."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT last_polled_at FROM user_channel_watermarks WHERE channel_id = $1",
                channel_id,
            )
        if row is None:
            return datetime.now(timezone.utc) - timedelta(
                hours=self.DEFAULT_LOOKBACK_HOURS
            )
        return row["last_polled_at"]

    async def get_many(self, channel_ids: list[str]) -> dict[str, datetime]:
        """Batch-fetch watermarks; missing channels get the default lookback."""
        if not channel_ids:
            return {}
        default = datetime.now(timezone.utc) - timedelta(
            hours=self.DEFAULT_LOOKBACK_HOURS
        )
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT channel_id, last_polled_at
                FROM user_channel_watermarks
                WHERE channel_id = ANY($1::text[])
                """,
                channel_ids,
            )
        found = {r["channel_id"]: r["last_polled_at"] for r in rows}
        return {
            channel_id: found.get(channel_id, default) for channel_id in channel_ids
        }

    async def set(self, channel_id: str, polled_at: datetime) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_channel_watermarks (channel_id, last_polled_at)
                VALUES ($1, $2)
                ON CONFLICT (channel_id) DO UPDATE SET last_polled_at = EXCLUDED.last_polled_at
                """,
                channel_id,
                polled_at,
            )

    async def record_outcome(
        self, channel_id: str, outcome: PollOutcome, at: datetime
    ) -> None:
        """Record a poll outcome without moving the watermark.

        With no row yet the insert starts at the lookback window, so the next
        successful poll still sees mail that arrived while polling failed.
        """
        async with self._pool.acquire() as conn:
            updated = await conn.execute(
                """
                UPDATE user_channel_watermarks
                SET last_outcome = $2, last_outcome_at = $3
                WHERE channel_id = $1
                """,
                channel_id,
                outcome.value,
                at,
            )
            if updated == "UPDATE 0":
                await conn.execute(
                    """
                    INSERT INTO user_channel_watermarks
                        (channel_id, last_polled_at, last_outcome, last_outcome_at)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (channel_id) DO UPDATE SET
                        last_outcome    = EXCLUDED.last_outcome,
                        last_outcome_at = EXCLUDED.last_outcome_at
                    """,
                    channel_id,
                    datetime.now(timezone.utc)
                    - timedelta(hours=self.DEFAULT_LOOKBACK_HOURS),
                    outcome.value,
                    at,
                )

    async def get_status_many(
        self, channel_ids: list[str]
    ) -> dict[str, ChannelPollStatus]:
        if not channel_ids:
            return {}
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT channel_id, last_polled_at, last_outcome, last_outcome_at
                FROM user_channel_watermarks
                WHERE channel_id = ANY($1::text[])
                """,
                channel_ids,
            )
        found = {
            r["channel_id"]: ChannelPollStatus(
                watermark=r["last_polled_at"],
                last_outcome=PollOutcome(r["last_outcome"])
                if r["last_outcome"]
                else None,
                last_outcome_at=r["last_outcome_at"],
            )
            for r in rows
        }
        empty = ChannelPollStatus(
            watermark=None, last_outcome=None, last_outcome_at=None
        )
        return {channel_id: found.get(channel_id, empty) for channel_id in channel_ids}
