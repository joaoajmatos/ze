from __future__ import annotations

from typing import Any

from ze_logging import get_logger
from ze_core.telemetry.types import CostRecord

log = get_logger(__name__)


class PostgresCostStore:
    def __init__(self, pool: Any) -> None:
        self._pool = pool
        # Conservative default: assume there may be rows left over from a previous
        # process run so the reconciler always queries on first startup.
        self._has_pending_writes: bool = True

    @property
    def has_pending_writes(self) -> bool:
        return self._has_pending_writes

    def mark_clean(self) -> None:
        self._has_pending_writes = False

    async def write(self, rec: CostRecord) -> None:
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO llm_cost_log
                        (session_id, agent, flow_type, model,
                         prompt_tokens, completion_tokens, total_tokens,
                         cost_usd, duration_ms, generation_id, audio_seconds)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                    """,
                    rec.session_id,
                    rec.agent,
                    rec.flow_type,
                    rec.model,
                    rec.prompt_tokens,
                    rec.completion_tokens,
                    rec.total_tokens,
                    rec.cost_usd,
                    rec.duration_ms,
                    rec.generation_id,
                    rec.audio_seconds,
                )
            if rec.generation_id is not None:
                self._has_pending_writes = True
        except Exception as exc:
            log.warning("cost_write_failed", error=str(exc))

    async def fetch_pending(
        self,
        batch_size: int,
        min_age_seconds: int,
        max_age_seconds: int,
        exclude_generation_ids: list[str] | None = None,
    ) -> list[dict]:
        """Unpriced rows inside the recency window, newest first.

        Newest first and the window keep rows OpenRouter has no record of from
        starving the rows it can still price.
        """
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT id, generation_id
                FROM llm_cost_log
                WHERE cost_usd IS NULL
                  AND generation_id IS NOT NULL
                  AND created_at < NOW() - ($1 * INTERVAL '1 second')
                  AND created_at > NOW() - ($2 * INTERVAL '1 second')
                  AND generation_id <> ALL($3::text[])
                ORDER BY created_at DESC
                LIMIT $4
                """,
                min_age_seconds,
                max_age_seconds,
                exclude_generation_ids or [],
                batch_size,
            )

    async def update_cost(self, row_id: Any, cost_usd: float) -> bool:
        async with self._pool.acquire() as conn:
            status = await conn.execute(
                "UPDATE llm_cost_log SET cost_usd = $1 WHERE id = $2",
                cost_usd,
                row_id,
            )
        return status == "UPDATE 1"

    async def fetch_session_usage(self, session_id: str) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT model, prompt_tokens, completion_tokens"
                " FROM llm_cost_log WHERE session_id = $1",
                session_id,
            )
        return [dict(row) for row in rows]

    async def fetch_daily_usage(self) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT model, prompt_tokens, completion_tokens"
                " FROM llm_cost_log WHERE created_at >= CURRENT_DATE"
            )
        return [dict(row) for row in rows]
