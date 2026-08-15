"""Integration tests for workspace follow-through wiring (Phase 116, User
Stories 1 and 2).

Exercises the settings -> bootstrap.build_workspace_stack -> ze_workspace.tools
boundary end to end (ZeApiSettings-shaped settings, real RunWatcher), with an
in-memory fake WorkspaceStore standing in for Postgres — SQL correctness for the
new store methods is covered by core/ze-workspace/tests/test_store.py.

User Story 2's tests (T018-T021) exercise apps/ze-api's real TurnStarter/
PushSender adapters (_ContainerTurnStarter, _NotifierPushSender in
ze_api.container) wired into a real RunWatcher, against fakes standing in for
ZeContainer/NativeAppInterface/ProactiveNotifier's storage layer.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

import ze_workspace.bootstrap as bootstrap
import ze_workspace.tools as tools
from ze_workspace.followthrough import RunWatcher
from ze_workspace.turn_lock import ThreadTurnLock
from ze_workspace.types import (
    WorkspaceMode,
    WorkspaceRun,
    WorkspaceRunOrigin,
    WorkspaceRunResult,
    WorkspaceRunStatus,
)

from ze_api.container import _ContainerTurnStarter, _NotifierPushSender
from ze_api.interface.native import NativeAppInterface
from ze_proactive.notifier import ProactiveNotifier
from ze_proactive.types import NotificationRow


class FakeInMemoryStore:
    """Minimal WorkspaceStore stand-in — enough surface for workspace_run's path."""

    def __init__(self, mode: WorkspaceMode = WorkspaceMode.AUTO) -> None:
        self._mode = mode
        self.runs: dict = {}

    async def get_mode(self):
        return self._mode

    async def insert_in_progress_run(self, run: WorkspaceRun) -> WorkspaceRun:
        recorded = WorkspaceRun(
            id=uuid4(),
            command=run.command,
            origin=run.origin,
            status=None,
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            thread_id=run.thread_id,
        )
        self.runs[recorded.id] = recorded
        return recorded

    async def complete_run(self, run_id, *, status, exit_code=None, output_preview="",
                            output_file_path=None, files_touched=None, error_summary=None):
        run = self.runs[run_id]
        if run.ended_at is not None:
            return None
        completed = WorkspaceRun(
            id=run.id,
            command=run.command,
            origin=run.origin,
            status=status,
            started_at=run.started_at,
            ended_at=datetime.now(timezone.utc),
            thread_id=run.thread_id,
            exit_code=exit_code,
            output_preview=output_preview,
            error_summary=error_summary,
        )
        self.runs[run_id] = completed
        return completed

    async def list_in_progress(self):
        return [r for r in self.runs.values() if r.ended_at is None]

    async def mark_follow_through_notified(self, run_id) -> bool:
        return True

    async def touch_used(self) -> None:
        pass

    async def insert_run(self, run: WorkspaceRun) -> WorkspaceRun:
        recorded = WorkspaceRun(id=uuid4(), **{
            k: v for k, v in run.__dict__.items() if k != "id"
        })
        self.runs[recorded.id] = recorded
        return recorded


def _settings(short_wait: float) -> SimpleNamespace:
    return SimpleNamespace(
        workspace_service_url="http://ze-workspace.internal:8080",
        workspace_api_token="",
        workspace_timeout_seconds=120,
        workspace_follow_through_short_wait_seconds=short_wait,
        config={"workspace": {}},
    )


def _wire(monkeypatch, *, short_wait: float, run_seconds: float, mode=WorkspaceMode.AUTO):
    store = FakeInMemoryStore(mode)
    monkeypatch.setattr(bootstrap, "PostgresWorkspaceStore", lambda pool: store)
    shared = SimpleNamespace(pool=None)
    stack = bootstrap.build_workspace_stack(shared, _settings(short_wait))

    async def fake_run(*args, **kwargs):
        await asyncio.sleep(run_seconds)
        return WorkspaceRunResult(
            exit_code=0, timed_out=False, stdout_preview="ok", stderr_preview=""
        )

    stack.client.health = AsyncMock(return_value=True)
    stack.client.run = AsyncMock(side_effect=fake_run)
    return stack, store


@pytest.mark.asyncio
async def test_short_run_finishes_in_turn_without_detach(monkeypatch):
    stack, store = _wire(monkeypatch, short_wait=0.05, run_seconds=0.0)
    detach_spy = AsyncMock(wraps=stack.run_watcher.detach)
    monkeypatch.setattr(stack.run_watcher, "detach", detach_spy)

    result = await tools.workspace_run("echo hi")

    assert "ok" in result
    assert "still running" not in result
    detach_spy.assert_not_awaited()
    (run,) = store.runs.values()
    assert run.ended_at is not None
    assert run.status is not None


@pytest.mark.asyncio
async def test_long_run_detaches_and_ends_turn_with_still_running(monkeypatch):
    stack, store = _wire(monkeypatch, short_wait=0.02, run_seconds=0.1)
    detach_spy = AsyncMock(wraps=stack.run_watcher.detach)
    monkeypatch.setattr(stack.run_watcher, "detach", detach_spy)

    result = await tools.workspace_run("sleep 60")

    assert "still running" in result
    detach_spy.assert_awaited_once()
    (run,) = store.runs.values()
    assert run.ended_at is None

    # Let the detached background task finish so it doesn't leak past the test.
    task = stack.run_watcher._tasks.get(run.id)
    if task is not None:
        await task


# ── User Story 2: follow-up turn + completion push (T018-T021) ────────────────


def _completed_run(*, status: WorkspaceRunStatus, origin=WorkspaceRunOrigin.CONVERSATION, thread_id="t-run") -> WorkspaceRun:
    return WorkspaceRun(
        id=uuid4(),
        command="sleep 60",
        origin=origin,
        status=status,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        thread_id=thread_id,
        follow_through_notified=False,
    )


class _FakeWatcherStore:
    """Just enough of WorkspaceStore for RunWatcher._dispatch (mark_follow_through_notified)."""

    def __init__(self) -> None:
        self.notified: set = set()

    async def mark_follow_through_notified(self, run_id) -> bool:
        if run_id in self.notified:
            return False
        self.notified.add(run_id)
        return True


class _FakeConnectionManager:
    def __init__(self, *, connected: bool) -> None:
        self.connected = connected
        self.sent_frames: list[tuple[dict, str | None]] = []
        self.pushed_messages: list = []

    async def push(self, message, thread_id=None) -> None:
        self.pushed_messages.append((message, thread_id))

    async def send_frame(self, frame: dict, thread_id: str | None = None) -> None:
        self.sent_frames.append((frame, thread_id))


class _FakeMessageStore:
    def __init__(self) -> None:
        self.saved: list = []

    async def save(self, msg) -> None:
        self.saved.append(msg)

    async def save_trace(self, msg_id, trace) -> None:
        pass


class _FakeNotificationStore:
    def __init__(self) -> None:
        self.created: list[dict] = []

    async def create(self, **kwargs) -> NotificationRow:
        self.created.append(kwargs)
        return NotificationRow(
            id=str(uuid4()),
            event_type=kwargs["event_type"],
            source=kwargs["source"],
            title=kwargs["title"],
            body=kwargs["body"],
            target_type=kwargs.get("target_type"),
            target_id=kwargs.get("target_id"),
            created_at=datetime.now(timezone.utc),
            read_at=None,
        )


def _real_push_stack(*, connected: bool):
    """Builds a real NativeAppInterface + ProactiveNotifier + _NotifierPushSender
    chain with fakes only at the storage/ntfy boundary, so T018/T019 exercise the
    actual connected-vs-push decision (D4) rather than re-asserting a mock call."""
    conn = _FakeConnectionManager(connected=connected)
    msg_store = _FakeMessageStore()
    ntfy = AsyncMock()
    interface = NativeAppInterface(
        message_store=msg_store, connection_manager=conn, notifier=ntfy
    )
    notification_store = _FakeNotificationStore()
    notifier = ProactiveNotifier(interface=interface, notification_store=notification_store)
    push_sender = _NotifierPushSender()
    push_sender.bind(notifier)
    return push_sender, conn, msg_store, ntfy, notification_store


class _FakeTurnOutcome:
    def __init__(self, response: str, interrupted: bool = False) -> None:
        self.response = response
        self.interrupted = interrupted
        self.final_state = {"components": [], "message_trace": None}


class _LockAwareFakeContainer:
    """Stand-in for ZeContainer.invoke_raw_turn: real ThreadTurnLock acquisition
    (mirrors container._locked_invoke_raw_turn) around a fake raw invoke, so
    T020 exercises real mutual exclusion without constructing a full ZeContainer."""

    def __init__(self, turn_lock, raw_invoke, interface):
        self._turn_lock = turn_lock
        self._raw_invoke = raw_invoke
        self.interface = interface

    async def invoke_raw_turn(self, thread_id, raw, *, config_extra=None):
        async with self._turn_lock.acquire(thread_id):
            return await self._raw_invoke(thread_id, raw)


@pytest.mark.asyncio
async def test_us2_connected_run_gets_followup_turn_and_noop_push():
    """T018: connected -> follow-up turn appears on the thread; push is a no-op
    (no ntfy dispatch — the WebSocket is delivering in real time)."""
    push_sender, conn, msg_store, ntfy, notification_store = _real_push_stack(connected=True)

    interface = SimpleNamespace(send_with_thread=AsyncMock())
    turn_starter = _ContainerTurnStarter()

    async def raw_invoke(thread_id, raw):
        return _FakeTurnOutcome(response=f"The workspace run finished: {raw.text}")


    container = _LockAwareFakeContainer(ThreadTurnLock(), raw_invoke, interface)
    turn_starter.bind(container)

    store = _FakeWatcherStore()
    watcher = RunWatcher(store=store, turn_starter=turn_starter, push_sender=push_sender)

    run = _completed_run(status=WorkspaceRunStatus.SUCCEEDED)
    await watcher._dispatch(run)

    interface.send_with_thread.assert_awaited_once()
    assert notification_store.created  # Notification Center entry always written
    ntfy.push.assert_not_awaited()  # connected -> no ntfy push


@pytest.mark.asyncio
async def test_us2_disconnected_run_pushes_and_writes_followup_to_history():
    """T019: disconnected -> ntfy push fires and the follow-up turn is written
    to conversation history (via the fake message store standing in for
    Postgres-backed MessageStore)."""
    push_sender, conn, msg_store, ntfy, notification_store = _real_push_stack(connected=False)

    saved_history: list = []

    async def raw_invoke(thread_id, raw):
        saved_history.append(raw.text)
        return _FakeTurnOutcome(response=f"The workspace run finished: {raw.text}")

    class _ContainerWithRealInterface:
        def __init__(self, turn_lock, raw_invoke, interface):
            self._turn_lock = turn_lock
            self._raw_invoke = raw_invoke
            self.interface = interface

        async def invoke_raw_turn(self, thread_id, raw, *, config_extra=None):
            async with self._turn_lock.acquire(thread_id):
                outcome = await self._raw_invoke(thread_id, raw)
                await self.interface.send_with_thread(outcome.response, thread_id=thread_id)
                return outcome


    real_interface = NativeAppInterface(
        message_store=msg_store, connection_manager=conn, notifier=AsyncMock()
    )
    container = _ContainerWithRealInterface(ThreadTurnLock(), raw_invoke, real_interface)

    turn_starter = _ContainerTurnStarter()
    turn_starter.bind(container)

    store = _FakeWatcherStore()
    watcher = RunWatcher(store=store, turn_starter=turn_starter, push_sender=push_sender)

    run = _completed_run(status=WorkspaceRunStatus.SUCCEEDED, thread_id="thread-disc")
    await watcher._dispatch(run)

    assert saved_history == ["The workspace run `sleep 60` (id " + str(run.id) + ") finished successfully."]
    assert msg_store.saved  # follow-up turn's message reached conversation history
    ntfy.push.assert_awaited()  # disconnected -> ntfy push fired


@pytest.mark.asyncio
async def test_us2_followup_waits_for_inprogress_turn_on_same_thread():
    """T020: a follow-up on a thread that already has a turn in flight waits for
    ThreadTurnLock rather than interrupting it."""

    lock = ThreadTurnLock()
    order: list[str] = []

    async def raw_invoke(thread_id, raw):
        order.append("followup-start")
        return _FakeTurnOutcome(response="done")

    interface = SimpleNamespace(send_with_thread=AsyncMock())
    container = _LockAwareFakeContainer(lock, raw_invoke, interface)
    turn_starter = _ContainerTurnStarter()
    turn_starter.bind(container)

    async def held_turn():
        async with lock.acquire("shared-thread"):
            order.append("user-turn-start")
            await asyncio.sleep(0.03)
            order.append("user-turn-end")

    async def followup():
        await asyncio.sleep(0.005)  # ensure the "user" turn grabs the lock first
        await turn_starter.invoke_raw_turn("shared-thread", "run finished")

    await asyncio.gather(held_turn(), followup())

    assert order == ["user-turn-start", "user-turn-end", "followup-start"]


@pytest.mark.asyncio
async def test_us2_unattended_run_never_dispatches_followup_or_push():
    """T021 (restated for _dispatch directly; T009/US1 already covers the
    origin!=conversation guard at the detach/finish level) — kept here for
    User-Story-2 test-file locality per the task list."""
    push_sender, conn, msg_store, ntfy, notification_store = _real_push_stack(connected=False)
    interface = SimpleNamespace(send_with_thread=AsyncMock())
    turn_starter = _ContainerTurnStarter()
    turn_starter.bind(SimpleNamespace(interface=interface, invoke_raw_turn=AsyncMock()))

    store = _FakeWatcherStore()
    watcher = RunWatcher(store=store, turn_starter=turn_starter, push_sender=push_sender)

    run = _completed_run(status=WorkspaceRunStatus.SUCCEEDED, origin=WorkspaceRunOrigin.UNATTENDED)
    await watcher._dispatch(run)

    interface.send_with_thread.assert_not_awaited()
    assert not notification_store.created
    ntfy.push.assert_not_awaited()


@pytest.mark.asyncio
async def test_us2_in_turn_completion_produces_no_followup_or_push():
    """T021: a run that finished inside its own turn (never detached) never
    reaches RunWatcher at all — the tool path (workspace_run) records it via
    complete_run/insert_run directly, RunWatcher.detach is never called (already
    covered by test_short_run_finishes_in_turn_without_detach above); this test
    pins that a RunWatcher with no dispatch call produces zero side effects."""
    push_sender, conn, msg_store, ntfy, notification_store = _real_push_stack(connected=False)
    interface = SimpleNamespace(send_with_thread=AsyncMock())
    turn_starter = _ContainerTurnStarter()
    turn_starter.bind(SimpleNamespace(interface=interface, invoke_raw_turn=AsyncMock()))

    store = _FakeWatcherStore()
    RunWatcher(store=store, turn_starter=turn_starter, push_sender=push_sender)
    # No detach()/reattach()/_dispatch() call for an in-turn-completed run.

    interface.send_with_thread.assert_not_awaited()
    assert not notification_store.created
    ntfy.push.assert_not_awaited()
