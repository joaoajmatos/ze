"""ActionRecorder links an undo to the action it reverses (Phase 180 T013)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ze_agents.rollback import RollbackScope, rollback_scope
from ze_memory.action_records.recorder import ActionRecorder
from ze_memory.action_records.types import ActionLifecycle, ActionOutcome
from tests.action_records.test_recorder import InMemoryActionRecordStore


class _Store(InMemoryActionRecordStore):
    def __init__(self, fail_list: bool = False) -> None:
        super().__init__()
        self.fail_list = fail_list
        self.list_calls = 0

    async def list(self, **kwargs):
        self.list_calls += 1
        if self.fail_list:
            raise RuntimeError("db")
        return sorted(
            self.by_id.values(), key=lambda r: r.occurred_at, reverse=True
        )


def _kw(action_kind: str, lifecycle=ActionLifecycle.SUCCEEDED, **extra):
    outcome = {
        ActionLifecycle.SUCCEEDED: ActionOutcome.SUCCESS,
        ActionLifecycle.CANCELLED: ActionOutcome.CANCELLED,
    }.get(lifecycle)
    return dict(
        producer_kind="reminder",
        source_record_type="reminder",
        source_record_id="r1",
        action_kind=action_kind,
        lifecycle=lifecycle,
        outcome=outcome,
        actor="ze",
        producer_plugin="ze-calendar",
        occurred_at=datetime.now(timezone.utc),
        summary="s",
        **extra,
    )


async def test_cancel_under_scope_supersedes_the_create_and_marks_message():
    store = _Store()
    recorder = ActionRecorder(store)
    created = await recorder.record_action(**_kw("set"))
    mid = uuid4()
    with rollback_scope(RollbackScope(retried_message_id=mid)):
        undo = await recorder.record_action(**_kw("cancel"))
    assert undo.supersedes == created.id
    assert undo.context.message_id == mid
    assert store.list_calls == 2


async def test_no_scope_leaves_behavior_unchanged():
    store = _Store()
    recorder = ActionRecorder(store)
    await recorder.record_action(**_kw("set"))
    undo = await recorder.record_action(**_kw("cancel"))
    assert undo.supersedes is None
    assert undo.context.message_id is None


async def test_same_action_type_is_not_superseded():
    store = _Store()
    recorder = ActionRecorder(store)
    await recorder.record_action(**_kw("set"))
    with rollback_scope(RollbackScope(retried_message_id=uuid4())):
        again = await recorder.record_action(
            **_kw("set", lifecycle=ActionLifecycle.CANCELLED)
        )
    assert again.supersedes is None


async def test_only_succeeded_records_are_superseded():
    store = _Store()
    recorder = ActionRecorder(store)
    await recorder.record_action(**_kw("set", lifecycle=ActionLifecycle.CANCELLED))
    with rollback_scope(RollbackScope(retried_message_id=uuid4())):
        undo = await recorder.record_action(**_kw("cancel"))
    assert undo.supersedes is None


async def test_lookup_failure_still_writes_the_record():
    store = _Store(fail_list=True)
    recorder = ActionRecorder(store)
    mid = uuid4()
    with rollback_scope(RollbackScope(retried_message_id=mid)):
        undo = await recorder.record_action(**_kw("cancel"))
    assert undo.supersedes is None
    assert undo.context.message_id == mid
    assert store.append_calls == 1


async def test_non_terminal_record_under_scope_gets_message_id_only():
    store = _Store()
    recorder = ActionRecorder(store)
    mid = uuid4()
    with rollback_scope(RollbackScope(retried_message_id=mid)):
        rec = await recorder.record_action(
            **_kw("cancel", lifecycle=ActionLifecycle.STARTED)
        )
    assert rec.supersedes is None
    assert rec.context.message_id == mid
    assert store.list_calls == 0
