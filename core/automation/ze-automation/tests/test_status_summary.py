from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_automation.rest import build_status_summary
from ze_automation.workflow.types import WorkflowFailure


def _failure(name: str) -> WorkflowFailure:
    return WorkflowFailure(
        workflow_id=uuid4(),
        workflow_name=name,
        execution_id=uuid4(),
        failed_at=datetime.now(timezone.utc),
        error="boom",
    )


def _container(failures: list[WorkflowFailure]) -> SimpleNamespace:
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value={"total_cost": 0})
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)
    workflow_store = AsyncMock()
    workflow_store.list_failed_executions = AsyncMock(return_value=failures)
    return SimpleNamespace(pool=pool, _plugin_stores={}, workflow_store=workflow_store)


async def test_status_lists_every_failed_run_of_one_workflow():
    container = _container([_failure("Weekly invoices"), _failure("Weekly invoices")])

    text = await build_status_summary(container, period_days=7)

    assert text.count("Failed: Weekly invoices") == 2
    container.workflow_store.list_failed_executions.assert_awaited_once_with(7 * 24)


async def test_status_without_failures_says_so():
    text = await build_status_summary(_container([]), period_days=1)

    assert "no failures" in text
