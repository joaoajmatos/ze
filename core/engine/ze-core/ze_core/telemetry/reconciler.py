from __future__ import annotations

from typing import Any

from ze_agents.errors import GenerationUnavailableError
from ze_logging import get_logger
from ze_core.telemetry.postgres import PostgresCostStore

_BATCH_SIZE = 100
_MIN_AGE_SECONDS = 120
_MAX_AGE_SECONDS = 3 * 86400
_UNAVAILABLE_CAP = 5000

log = get_logger(__name__)


class CostReconciler:
    """Backfills cost_usd on llm_cost_log rows that have a generation_id but no cost yet.

    Requires a PostgresCostStore and an OpenRouterClient. Each run prices up to 100
    rows, newest first, skipping rows younger than 2 minutes (OpenRouter may lag) and
    older than 3 days (OpenRouter keeps no record of them). A generation OpenRouter
    answers "no record" for is remembered for the life of the process and not asked
    again.
    """

    def __init__(self, store: PostgresCostStore, openrouter_client: Any) -> None:
        self._store = store
        self._client = openrouter_client
        self._unavailable: set[str] = set()

    async def run(self) -> None:
        if not self._store.has_pending_writes:
            return

        rows = await self._store.fetch_pending(
            batch_size=_BATCH_SIZE,
            min_age_seconds=_MIN_AGE_SECONDS,
            max_age_seconds=_MAX_AGE_SECONDS,
            exclude_generation_ids=sorted(self._unavailable),
        )

        if not rows:
            self._store.mark_clean()
            return

        log.info("cost_reconcile_start", count=len(rows))
        updated = 0
        unavailable = 0

        for row in rows:
            try:
                cost = await self._client.fetch_generation_cost(row["generation_id"])
            except GenerationUnavailableError:
                unavailable += 1
                if len(self._unavailable) < _UNAVAILABLE_CAP:
                    self._unavailable.add(row["generation_id"])
                continue
            if cost is None:
                continue
            if await self._store.update_cost(row["id"], cost):
                updated += 1
            else:
                log.warning(
                    "cost_reconcile_update_changed_no_row",
                    row_id=str(row["id"]),
                    generation_id=row["generation_id"],
                )

        log.info(
            "cost_reconcile_done",
            updated=updated,
            unavailable=unavailable,
            skipped=len(rows) - updated - unavailable,
        )
