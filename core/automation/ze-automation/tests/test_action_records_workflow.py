from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from ze_memory.action_records.types import ActionLifecycle

from ze_automation.action_records import configure_action_recorder
from ze_automation.workflow.postgres import PostgresWorkflowStore
from test_action_records import InMemoryActionRecordStore, _pool


@pytest.fixture
def ledger():
    store = InMemoryActionRecordStore()
    configure_action_recorder(store)
    yield store
    configure_action_recorder(None)


async def test_finish_returns_workflow_id_and_stamps_both_ids(
    ledger: InMemoryActionRecordStore,
):
    execution_id, workflow_id = uuid4(), uuid4()
    pool, conn = _pool(fetchrow={"workflow_id": workflow_id})
    await PostgresWorkflowStore(pool).finish_execution(execution_id, "completed")

    sql = " ".join(conn.fetchrow.await_args.args[0].split())
    assert sql.startswith("UPDATE workflow_executions")
    assert "RETURNING workflow_id" in sql
    record = next(iter(ledger.by_key.values()))
    assert record.lifecycle is ActionLifecycle.SUCCEEDED
    assert record.context.workflow_id == workflow_id
    assert record.context.workflow_run_id == execution_id


async def test_finish_without_row_still_emits_and_logs(
    ledger: InMemoryActionRecordStore,
):
    execution_id = uuid4()
    pool, _ = _pool(fetchrow=None)
    with patch("ze_automation.workflow.postgres.log") as log:
        await PostgresWorkflowStore(pool).finish_execution(execution_id, "failed")

    record = next(iter(ledger.by_key.values()))
    assert record.lifecycle is ActionLifecycle.FAILED
    assert record.context.workflow_id is None
    assert record.context.workflow_run_id == execution_id
    assert log.warning.called or log.info.called
