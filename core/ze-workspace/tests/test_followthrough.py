from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


from ze_workspace.followthrough import RunWatcher
from ze_workspace.types import (
    WorkspaceRun,
    WorkspaceRunOrigin,
    WorkspaceRunResult,
    WorkspaceRunStatus,
)


class FakeStore:
    def __init__(self) -> None:
        self.completed: list[dict] = []
        self.notified: set = set()
        self.runs: dict = {}

    async def complete_run(self, run_id, *, status, exit_code=None, output_preview="",
                            output_file_path=None, files_touched=None, error_summary=None):
        run = self.runs.get(run_id)
        if run is None or run.ended_at is not None:
            return None
        completed = WorkspaceRun(
            id=run_id,
            command=run.command,
            origin=run.origin,
            status=status,
            started_at=run.started_at,
            ended_at=datetime.now(timezone.utc),
            thread_id=run.thread_id,
            exit_code=exit_code,
            output_preview=output_preview,
            files_touched=files_touched or [],
            error_summary=error_summary,
        )
        self.runs[run_id] = completed
        self.completed.append({"run_id": run_id, "status": status})
        return completed

    async def mark_follow_through_notified(self, run_id) -> bool:
        if run_id in self.notified:
            return False
        self.notified.add(run_id)
        return True

    async def cancel_run(self, run_id):
        run = self.runs.get(run_id)
        if run is None or run.ended_at is not None:
            return None
        cancelled = WorkspaceRun(
            id=run_id,
            command=run.command,
            origin=run.origin,
            status=WorkspaceRunStatus.CANCELLED,
            started_at=run.started_at,
            ended_at=datetime.now(timezone.utc),
            thread_id=run.thread_id,
            output_preview=run.output_preview,
            files_touched=run.files_touched,
        )
        self.runs[run_id] = cancelled
        return cancelled


class FakeTurnStarter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def invoke_raw_turn(self, thread_id: str, prompt: str) -> None:
        self.calls.append((thread_id, prompt))


class FakePushSender:
    def __init__(self) -> None:
        self.calls: list[WorkspaceRun] = []

    async def send_completion(self, run: WorkspaceRun) -> None:
        self.calls.append(run)


class FakeCompletionSource:
    def __init__(self, result: WorkspaceRunResult) -> None:
        self._result = result
        self.calls = 0

    async def await_completion(self, run: WorkspaceRun) -> WorkspaceRunResult:
        self.calls += 1
        return self._result


def _run(origin=WorkspaceRunOrigin.CONVERSATION, thread_id="t1") -> WorkspaceRun:
    return WorkspaceRun(
        id=uuid4(),
        command="sleep 60",
        origin=origin,
        status=None,
        started_at=datetime.now(timezone.utc),
        ended_at=None,
        thread_id=thread_id,
    )


async def _detach_and_wait(watcher: RunWatcher, store: FakeStore, run, result) -> None:
    store.runs[run.id] = run

    async def pending():
        return result

    await watcher.detach(run, pending())
    task = watcher._tasks.get(run.id)
    if task is not None:
        await task


async def test_detach_dispatches_followup_and_push_once():
    store = FakeStore()
    turn_starter = FakeTurnStarter()
    push_sender = FakePushSender()
    watcher = RunWatcher(store, turn_starter, push_sender)
    run = _run()
    result = WorkspaceRunResult(exit_code=0, timed_out=False, stdout_preview="ok", stderr_preview="")

    await _detach_and_wait(watcher, store, run, result)

    assert len(turn_starter.calls) == 1
    assert turn_starter.calls[0][0] == "t1"
    assert len(push_sender.calls) == 1
    assert store.completed[0]["status"] is WorkspaceRunStatus.SUCCEEDED


async def test_origin_not_conversation_never_dispatches():
    store = FakeStore()
    turn_starter = FakeTurnStarter()
    push_sender = FakePushSender()
    watcher = RunWatcher(store, turn_starter, push_sender)
    run = _run(origin=WorkspaceRunOrigin.UNATTENDED)
    result = WorkspaceRunResult(exit_code=0, timed_out=False, stdout_preview="ok", stderr_preview="")

    await _detach_and_wait(watcher, store, run, result)

    assert turn_starter.calls == []
    assert push_sender.calls == []
    # The run is still marked complete in the store, just not followed through.
    assert store.completed[0]["status"] is WorkspaceRunStatus.SUCCEEDED


async def test_reattach_rederives_pending_completion():
    store = FakeStore()
    turn_starter = FakeTurnStarter()
    push_sender = FakePushSender()
    run = _run()
    store.runs[run.id] = run
    result = WorkspaceRunResult(exit_code=1, timed_out=False, stdout_preview="", stderr_preview="boom")
    completion_source = FakeCompletionSource(result)
    watcher = RunWatcher(store, turn_starter, push_sender, completion_source)

    await watcher.reattach(run)
    task = watcher._tasks.get(run.id)
    assert task is not None
    await task

    assert completion_source.calls == 1
    assert len(turn_starter.calls) == 1
    assert store.completed[0]["status"] is WorkspaceRunStatus.FAILED


async def test_reattach_without_completion_source_is_a_noop():
    store = FakeStore()
    turn_starter = FakeTurnStarter()
    push_sender = FakePushSender()
    watcher = RunWatcher(store, turn_starter, push_sender)
    run = _run()
    store.runs[run.id] = run

    await watcher.reattach(run)

    assert watcher._tasks == {}
    assert turn_starter.calls == []


async def test_cancel_dispatches_stopped_followup_not_success():
    store = FakeStore()
    turn_starter = FakeTurnStarter()
    push_sender = FakePushSender()
    watcher = RunWatcher(store, turn_starter, push_sender)
    run = _run()
    store.runs[run.id] = run

    cancelled = await watcher.cancel(run.id)

    assert cancelled is not None
    assert cancelled.status is WorkspaceRunStatus.CANCELLED
    assert len(turn_starter.calls) == 1
    assert "stopped" in turn_starter.calls[0][1]
    assert "finished successfully" not in turn_starter.calls[0][1]
    assert len(push_sender.calls) == 1


async def test_cancel_on_already_terminal_run_returns_none_and_does_not_redispatch():
    store = FakeStore()
    turn_starter = FakeTurnStarter()
    push_sender = FakePushSender()
    watcher = RunWatcher(store, turn_starter, push_sender)
    run = _run()
    store.runs[run.id] = run
    first = await watcher.cancel(run.id)
    assert first is not None

    second = await watcher.cancel(run.id)

    assert second is None
    # Still exactly one dispatch from the first cancel.
    assert len(turn_starter.calls) == 1
    assert len(push_sender.calls) == 1


async def test_cancel_races_in_flight_detach_without_double_dispatch():
    """A run that was already detached (RunWatcher._finish awaiting
    pending_completion) gets cancelled from the REST layer before the sidecar
    call returns. cancel() wins the race; when _finish's pending_completion
    eventually resolves, complete_run's WHERE ended_at IS NULL guard makes it
    a no-op — follow-through fires exactly once, for the cancellation."""
    store = FakeStore()
    turn_starter = FakeTurnStarter()
    push_sender = FakePushSender()
    watcher = RunWatcher(store, turn_starter, push_sender)
    run = _run()
    store.runs[run.id] = run
    result = WorkspaceRunResult(exit_code=0, timed_out=False, stdout_preview="ok", stderr_preview="")

    async def pending():
        return result

    await watcher.detach(run, pending())
    cancelled = await watcher.cancel(run.id)
    task = watcher._tasks.get(run.id)
    if task is not None:
        await task

    assert cancelled is not None
    assert cancelled.status is WorkspaceRunStatus.CANCELLED
    assert len(turn_starter.calls) == 1
    assert "stopped" in turn_starter.calls[0][1]
