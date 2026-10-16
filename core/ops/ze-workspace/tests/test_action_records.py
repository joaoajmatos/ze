from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_agents.claims import ClaimKind
from ze_memory.action_records.types import (
    ActionLifecycle,
    ActionOutcome,
    ActionRecordDraft,
)
from ze_plugin.contribution import SourceFunction

from ze_workspace.action_handoff import (
    configure_action_ledger,
    record_workspace_run,
)
from ze_workspace.types import WorkspaceRun, WorkspaceRunOrigin, WorkspaceRunStatus


def _run(**overrides) -> WorkspaceRun:
    now = datetime.now(timezone.utc)
    base = dict(
        id=uuid4(),
        command="echo hi",
        origin=WorkspaceRunOrigin.CONVERSATION,
        status=WorkspaceRunStatus.SUCCEEDED,
        started_at=now,
        ended_at=now,
        exit_code=0,
        output_preview="hi",
        error_summary=None,
    )
    base.update(overrides)
    return WorkspaceRun(**base)


async def _submitted(run: WorkspaceRun) -> ActionRecordDraft:
    store = AsyncMock()
    store.get = AsyncMock(return_value=None)
    store.append = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    configure_action_ledger(action_record_store=store, workspace_store=AsyncMock())
    await record_workspace_run(run)
    contribution = store.append.await_args.args[0]
    assert contribution.source_function is SourceFunction.ACTION
    assert contribution.claim_kind is ClaimKind.ACTION_RECORD
    return contribution.action_record


async def test_adapter_does_not_copy_command_or_output() -> None:
    draft = await _submitted(
        _run(command="cat /etc/passwd", output_preview="secret-output")
    )
    assert "passwd" not in draft.summary
    assert "secret-output" not in draft.summary
    assert draft.authoritative_ref.domain == "workspace.workspace_run"
    assert draft.lifecycle is ActionLifecycle.SUCCEEDED


async def test_failed_run_is_failed_not_success() -> None:
    draft = await _submitted(
        _run(status=WorkspaceRunStatus.FAILED, exit_code=1, error_summary="boom")
    )
    assert draft.lifecycle is ActionLifecycle.FAILED
    assert draft.outcome is ActionOutcome.FAILURE
    assert draft.failure_code == "nonzero_exit"


async def test_timeout_and_cancel_are_distinct() -> None:
    timeout = await _submitted(_run(status=WorkspaceRunStatus.TIMED_OUT))
    cancelled = await _submitted(_run(status=WorkspaceRunStatus.CANCELLED))
    assert timeout.lifecycle is ActionLifecycle.TIMED_OUT
    assert cancelled.lifecycle is ActionLifecycle.CANCELLED


async def test_in_progress_has_no_outcome() -> None:
    draft = await _submitted(_run(status=None, ended_at=None, exit_code=None))
    assert draft.lifecycle is ActionLifecycle.STARTED
    assert draft.outcome is None


async def test_lost_run_is_unknown() -> None:
    draft = await _submitted(
        _run(
            status=WorkspaceRunStatus.FAILED,
            error_summary="the computer restarted and lost this run — no fabricated result",
        )
    )
    assert draft.lifecycle is ActionLifecycle.UNKNOWN
    assert draft.outcome is ActionOutcome.UNKNOWN


async def test_duplicate_delivery_reuses_submit() -> None:
    store = AsyncMock()
    record = SimpleNamespace(id=uuid4())
    store.append = AsyncMock(return_value=record)
    store.get = AsyncMock(return_value=None)
    workspace_store = AsyncMock()
    configure_action_ledger(action_record_store=store, workspace_store=workspace_store)
    run = _run()
    first = await record_workspace_run(run)
    second = await record_workspace_run(run)
    assert first is not None
    assert second is not None
    assert workspace_store.mark_ledger_handoff.await_count >= 2


async def test_ledger_failure_does_not_rerun_and_stays_pending() -> None:
    store = AsyncMock()
    store.get = AsyncMock(return_value=None)

    async def boom(_contribution):
        raise RuntimeError("ledger down")

    store.append = boom
    workspace_store = AsyncMock()
    configure_action_ledger(action_record_store=store, workspace_store=workspace_store)
    result = await record_workspace_run(_run())
    assert result is None
    pending_marks = [
        call.kwargs["pending"]
        for call in workspace_store.mark_ledger_handoff.await_args_list
    ]
    assert True in pending_marks
    assert False not in pending_marks
