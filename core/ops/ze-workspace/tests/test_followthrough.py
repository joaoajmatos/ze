from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


from ze_workspace.followthrough import RunWatcher
from ze_workspace.types import (
    WorkspaceRun,
    WorkspaceRunOrigin,
    WorkspaceRunStatus,
    WorkspaceRunStatusDTO,
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


class FakeClient:
    """Stands in for WorkspaceClient's get_run/watch_run surface."""

    def __init__(self, *, events: list | None = None, status: WorkspaceRunStatusDTO | None = None,
                 get_run_fails: bool = False, watch_fails: Exception | None = None) -> None:
        self._events = events or []
        self._status = status
        self._get_run_fails = get_run_fails
        self._watch_fails = watch_fails
        self.get_run_calls = 0
        self.watch_calls = 0

    async def get_run(self, run_id):
        self.get_run_calls += 1
        if self._get_run_fails:
            return None
        return self._status

    async def watch_run(self, run_id):
        self.watch_calls += 1
        if self._watch_fails is not None:
            raise self._watch_fails
        for ev in self._events:
            yield ev


class FakeEvent:
    def __init__(self, type: str) -> None:
        self.type = type


def _run(origin=WorkspaceRunOrigin.CONVERSATION, thread_id="t1", **overrides) -> WorkspaceRun:
    base = dict(
        id=uuid4(),
        command="sleep 60",
        origin=origin,
        status=None,
        started_at=datetime.now(timezone.utc),
        ended_at=None,
        thread_id=thread_id,
        sidecar_dispatched=True,
    )
    base.update(overrides)
    return WorkspaceRun(**base)


def _status(**overrides) -> WorkspaceRunStatusDTO:
    base = dict(
        id=uuid4(),
        status="succeeded",
        exit_code=0,
        timed_out=False,
        stdout_preview="ok",
        stderr_preview="",
        output_file_path=None,
        files_touched=[],
    )
    base.update(overrides)
    return WorkspaceRunStatusDTO(**base)


async def _detach_and_wait(watcher: RunWatcher, store: FakeStore, run) -> None:
    store.runs[run.id] = run
    await watcher.detach(run)
    task = watcher._tasks.get(run.id)
    if task is not None:
        await task


async def test_detach_dispatches_followup_and_push_once():
    store = FakeStore()
    turn_starter = FakeTurnStarter()
    push_sender = FakePushSender()
    client = FakeClient(events=[FakeEvent("stdout"), FakeEvent("exit")], status=_status())
    watcher = RunWatcher(store, turn_starter, push_sender, client)
    run = _run()

    await _detach_and_wait(watcher, store, run)

    assert len(turn_starter.calls) == 1
    assert turn_starter.calls[0][0] == "t1"
    assert len(push_sender.calls) == 1
    assert store.completed[0]["status"] is WorkspaceRunStatus.SUCCEEDED


async def test_origin_not_conversation_never_dispatches():
    store = FakeStore()
    turn_starter = FakeTurnStarter()
    push_sender = FakePushSender()
    client = FakeClient(events=[FakeEvent("exit")], status=_status())
    watcher = RunWatcher(store, turn_starter, push_sender, client)
    run = _run(origin=WorkspaceRunOrigin.UNATTENDED)

    await _detach_and_wait(watcher, store, run)

    assert turn_starter.calls == []
    assert push_sender.calls == []
    # The run is still marked complete in the store, just not followed through.
    assert store.completed[0]["status"] is WorkspaceRunStatus.SUCCEEDED


async def test_detach_watch_failure_marks_failed_plain_language():
    store = FakeStore()
    turn_starter = FakeTurnStarter()
    push_sender = FakePushSender()
    client = FakeClient(watch_fails=ConnectionError("boom"))
    watcher = RunWatcher(store, turn_starter, push_sender, client)
    run = _run()

    await _detach_and_wait(watcher, store, run)

    assert store.completed[0]["status"] is WorkspaceRunStatus.FAILED
    assert "boom" in store.runs[run.id].error_summary


async def test_reattach_still_running_resumes_watching():
    store = FakeStore()
    turn_starter = FakeTurnStarter()
    push_sender = FakePushSender()
    run = _run()
    store.runs[run.id] = run
    client = FakeClient(events=[FakeEvent("exit")], status=_status())
    watcher = RunWatcher(store, turn_starter, push_sender, client)

    # First get_run (inside reattach) reports running, so it resumes via detach();
    # the FakeClient's second get_run call (inside _watch_to_terminal) reports terminal.
    calls = {"n": 0}

    async def get_run(run_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return _status(status="running", exit_code=None)
        return _status()

    client.get_run = get_run

    await watcher.reattach(run)
    task = watcher._tasks.get(run.id)
    assert task is not None
    await task

    assert len(turn_starter.calls) == 1
    assert store.completed[0]["status"] is WorkspaceRunStatus.SUCCEEDED


async def test_reattach_terminal_status_completes_directly():
    store = FakeStore()
    turn_starter = FakeTurnStarter()
    push_sender = FakePushSender()
    run = _run()
    store.runs[run.id] = run
    client = FakeClient(status=_status(status="failed", exit_code=1, stderr_preview="boom"))
    watcher = RunWatcher(store, turn_starter, push_sender, client)

    await watcher.reattach(run)

    assert watcher._tasks == {}
    assert len(turn_starter.calls) == 1
    assert store.completed[0]["status"] is WorkspaceRunStatus.FAILED


async def test_reattach_lost_handle_marks_failed_not_success():
    store = FakeStore()
    turn_starter = FakeTurnStarter()
    push_sender = FakePushSender()
    run = _run()
    store.runs[run.id] = run
    client = FakeClient(get_run_fails=True)
    watcher = RunWatcher(store, turn_starter, push_sender, client)

    await watcher.reattach(run)

    assert store.completed[0]["status"] is WorkspaceRunStatus.FAILED
    assert "restarted" in store.runs[run.id].error_summary


async def test_reattach_never_dispatched_marks_failed_without_client_call():
    store = FakeStore()
    turn_starter = FakeTurnStarter()
    push_sender = FakePushSender()
    run = _run(sidecar_dispatched=False)
    store.runs[run.id] = run
    client = FakeClient()
    watcher = RunWatcher(store, turn_starter, push_sender, client)

    await watcher.reattach(run)

    assert client.get_run_calls == 0
    assert client.watch_calls == 0
    assert store.completed[0]["status"] is WorkspaceRunStatus.FAILED


async def test_reattach_without_client_is_a_noop():
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
    """A run that was already detached (RunWatcher watching /events) gets
    cancelled from the REST layer before the watch loop observes the exit
    event. cancel() wins the race; when the watch loop's own completion write
    eventually lands, complete_run's WHERE ended_at IS NULL guard makes it a
    no-op — follow-through fires exactly once, for the cancellation."""
    store = FakeStore()
    turn_starter = FakeTurnStarter()
    push_sender = FakePushSender()
    run = _run()
    store.runs[run.id] = run

    import asyncio

    never_exits = asyncio.Event()

    class SlowClient(FakeClient):
        async def watch_run(self, run_id):
            self.watch_calls += 1
            await never_exits.wait()
            yield FakeEvent("exit")

    client = SlowClient(status=_status())
    watcher = RunWatcher(store, turn_starter, push_sender, client)

    await watcher.detach(run)
    cancelled = await watcher.cancel(run.id)
    never_exits.set()
    task = watcher._tasks.get(run.id)
    if task is not None:
        await task

    assert cancelled is not None
    assert cancelled.status is WorkspaceRunStatus.CANCELLED
    assert len(turn_starter.calls) == 1
    assert "stopped" in turn_starter.calls[0][1]


async def test_external_watcher_does_not_affect_followthrough_dispatch():
    """US2: a separate caller watching /runs/{id}/events concurrently (e.g.
    the ze-api events route) reads its own independent generator off the
    same client — it must not suppress or duplicate RunWatcher's own
    detach-driven follow-through dispatch."""
    store = FakeStore()
    turn_starter = FakeTurnStarter()
    push_sender = FakePushSender()
    client = FakeClient(events=[FakeEvent("stdout"), FakeEvent("exit")], status=_status())
    watcher = RunWatcher(store, turn_starter, push_sender, client)
    run = _run()
    store.runs[run.id] = run

    # A second, independent watcher reads its own copy of the stream —
    # RunWatcher.detach() below uses its own separate call to client.watch_run.
    external_events = [ev async for ev in client.watch_run(run.id)]
    assert [e.type for e in external_events] == ["stdout", "exit"]

    await _detach_and_wait(watcher, store, run)

    assert len(turn_starter.calls) == 1
    assert len(push_sender.calls) == 1
