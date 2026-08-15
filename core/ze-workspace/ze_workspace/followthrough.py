from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Protocol
from uuid import UUID

from ze_logging import get_logger

from ze_workspace.store import WorkspaceStore
from ze_workspace.types import (
    WorkspaceRun,
    WorkspaceRunOrigin,
    WorkspaceRunResult,
    WorkspaceRunStatus,
)

log = get_logger(__name__)


class TurnStarter(Protocol):
    async def invoke_raw_turn(self, thread_id: str, prompt: str) -> None:
        """Starts a normal follow-up turn on thread_id. Must internally acquire the
        ThreadTurnLock for thread_id before invoking the graph, and release it after —
        RunWatcher does not manage the lock itself, it only awaits this call."""
        ...


class PushSender(Protocol):
    async def send_completion(self, run: WorkspaceRun) -> None:
        """Delivers a completion notification. Internally decides connected-vs-push —
        RunWatcher always calls this unconditionally for a terminal
        origin=conversation run; the implementation is what makes it a no-op when
        the client is connected."""
        ...


class RunCompletionSource(Protocol):
    """Re-derives a pending completion for a run rediscovered at startup (D5) —
    supplied by apps/ze-api so RunWatcher.reattach can resume watching a run whose
    in-memory asyncio.Task was lost to a restart."""

    async def await_completion(self, run: WorkspaceRun) -> WorkspaceRunResult: ...


def _status_for_result(result: WorkspaceRunResult) -> WorkspaceRunStatus:
    if result.timed_out:
        return WorkspaceRunStatus.TIMED_OUT
    if result.exit_code == 0:
        return WorkspaceRunStatus.SUCCEEDED
    return WorkspaceRunStatus.FAILED


def _followup_prompt(run: WorkspaceRun) -> str:
    command = run.command
    if run.status is WorkspaceRunStatus.CANCELLED:
        return f"The workspace run `{command}` (id {run.id}) was stopped before it finished."
    if run.status is WorkspaceRunStatus.SUCCEEDED:
        return f"The workspace run `{command}` (id {run.id}) finished successfully."
    if run.status is WorkspaceRunStatus.TIMED_OUT:
        return f"The workspace run `{command}` (id {run.id}) timed out."
    return f"The workspace run `{command}` (id {run.id}) failed."


class RunWatcher:
    """Follows a detached workspace run to a terminal status, then dispatches
    follow-through (a follow-up turn and a completion push) for origin=conversation
    runs only (FR-015)."""

    def __init__(
        self,
        store: WorkspaceStore,
        turn_starter: TurnStarter,
        push_sender: PushSender,
        completion_source: RunCompletionSource | None = None,
    ) -> None:
        self._store = store
        self._turn_starter = turn_starter
        self._push_sender = push_sender
        self._completion_source = completion_source
        self._tasks: dict[UUID, asyncio.Task[Any]] = {}

    async def detach(
        self,
        run: WorkspaceRun,
        pending_completion: Awaitable[WorkspaceRunResult],
    ) -> None:
        """Called once the short wait elapses without pending_completion resolving.
        Schedules a background task that awaits pending_completion, persists the
        terminal status, then — only when run.origin == conversation — dispatches
        the follow-up turn and completion push."""
        if run.id is None:
            log.warning("workspace_run_detach_missing_id", command=run.command)
            return
        task = asyncio.create_task(self._finish(run, pending_completion))
        self._tasks[run.id] = task
        task.add_done_callback(lambda _t, rid=run.id: self._tasks.pop(rid, None))

    async def reattach(self, run: WorkspaceRun) -> None:
        """Startup reconciliation (D5): re-derives pending_completion for a run
        with ended_at IS NULL and calls detach() again. If follow_through_notified
        is already True on an otherwise-terminal row found at startup, this is not
        double-delivery — it is the one delivery that never went out."""
        if run.id is None:
            return
        if run.ended_at is not None:
            if not run.follow_through_notified:
                await self._dispatch(run)
            return
        if self._completion_source is None:
            log.warning(
                "workspace_run_reattach_no_completion_source", run_id=str(run.id)
            )
            return
        pending = self._completion_source.await_completion(run)
        await self.detach(run, pending)

    async def _finish(
        self,
        run: WorkspaceRun,
        pending_completion: Awaitable[WorkspaceRunResult],
    ) -> None:
        assert run.id is not None
        try:
            result = await pending_completion
        except Exception as exc:  # sidecar/network failure while detached
            log.warning(
                "workspace_run_detached_failed", run_id=str(run.id), error=str(exc)
            )
            completed = await self._store.complete_run(
                run.id,
                status=WorkspaceRunStatus.FAILED,
                error_summary=str(exc),
            )
        else:
            preview = result.stdout_preview or result.stderr_preview
            completed = await self._store.complete_run(
                run.id,
                status=_status_for_result(result),
                exit_code=result.exit_code,
                output_preview=preview,
                output_file_path=result.output_file_path,
                files_touched=result.files_touched,
                error_summary=result.stderr_preview if result.exit_code else None,
            )
        if completed is None:
            log.info("workspace_run_already_terminal", run_id=str(run.id))
            return
        await self._dispatch(completed)

    async def _dispatch(self, run: WorkspaceRun) -> None:
        if run.id is None or run.origin is not WorkspaceRunOrigin.CONVERSATION:
            return
        notified = await self._store.mark_follow_through_notified(run.id)
        if not notified:
            return
        if run.thread_id:
            await self._turn_starter.invoke_raw_turn(
                run.thread_id, _followup_prompt(run)
            )
        await self._push_sender.send_completion(run)
