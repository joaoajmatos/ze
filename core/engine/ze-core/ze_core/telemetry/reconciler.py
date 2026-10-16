from __future__ import annotations

from typing import Any

from ze_agents.errors import GenerationUnavailableError
from ze_logging import get_logger
from ze_core.telemetry.postgres import PostgresCostStore

_BATCH_SIZE = 100
_MIN_AGE_SECONDS = 120
_MAX_AGE_SECONDS = 3 * 86400
_UNAVAILABLE_CAP = 5000
_NOT_FOUND_MISSES = 3

log = get_logger(__name__)


class CostReconciler:
    """Backfills cost_usd on llm_cost_log rows that have a generation_id but no cost yet.

    Requires a PostgresCostStore and an OpenRouterClient. Each run prices up to 100
    rows, newest first, skipping rows younger than 2 minutes (OpenRouter may lag) and
    older than 3 days (OpenRouter keeps no record of them). An invalid generation id
    (HTTP 400) is remembered for the life of the process and not asked again. A 404
    may only mean OpenRouter has not indexed the generation yet, so it is retried each
    run and given up on after three misses in a row (about 30 minutes at the 15-minute
    cadence).
    """

    def __init__(self, store: PostgresCostStore, openrouter_client: Any) -> None:
        self._store = store
        self._client = openrouter_client
        self._unavailable: set[str] = set()
        self._not_found: dict[str, int] = {}

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
            except GenerationUnavailableError as exc:
                unavailable += 1
                self._record_miss(row["generation_id"], exc.status_code)
                continue
            self._not_found.pop(row["generation_id"], None)
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

    def _record_miss(self, generation_id: str, status_code: int | None) -> None:
        if status_code == 404:
            misses = self._not_found.get(generation_id, 0) + 1
            if misses < _NOT_FOUND_MISSES:
                self._not_found[generation_id] = misses
                return
            self._not_found.pop(generation_id, None)
        if len(self._unavailable) < _UNAVAILABLE_CAP:
            self._unavailable.add(generation_id)
