from __future__ import annotations

import asyncio
from typing import Any, Protocol
from uuid import UUID

from ze_logging import get_logger

from ze_workspace.store import WorkspaceStore
from ze_workspace.types import (
    WorkspaceRun,
    WorkspaceRunOrigin,
    WorkspaceRunStatus,
    WorkspaceRunStatusDTO,
)

log = get_logger(__name__)

_LOST_ON_RESTART_SUMMARY = (
    "the computer restarted and lost this run — no fabricated result"
)
_NEVER_DISPATCHED_SUMMARY = (
    "ze-api restarted before this run reached the workspace computer"
)

_STATUS_MAP = {
    "succeeded": WorkspaceRunStatus.SUCCEEDED,
    "failed": WorkspaceRunStatus.FAILED,
    "timed_out": WorkspaceRunStatus.TIMED_OUT,
    "cancelled": WorkspaceRunStatus.CANCELLED,
}


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


class RunStatusSource(Protocol):
    """The subset of WorkspaceClient RunWatcher needs — GET /runs/{id} and
    GET /runs/{id}/events (Phase 129). Kept as a narrow Protocol so tests can
    supply a fake without constructing a real httpx-backed WorkspaceClient."""

    async def get_run(self, run_id: UUID) -> WorkspaceRunStatusDTO | None: ...

    def watch_run(self, run_id: UUID) -> Any:
        """Returns an async iterator of JournalEventDTO."""
        ...


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
    """Follows a detached workspace run to a terminal status by watching its
    sidecar handle (Phase 129 — reads real output/exit data, no more guessing
    from /stat's busy flag), then dispatches follow-through (a follow-up turn
    and a completion push) for origin=conversation runs only (FR-015)."""

    def __init__(
        self,
        store: WorkspaceStore,
        turn_starter: TurnStarter,
        push_sender: PushSender,
        client: RunStatusSource | None = None,
    ) -> None:
        self._store = store
        self._turn_starter = turn_starter
        self._push_sender = push_sender
        self._client = client
        self._tasks: dict[UUID, asyncio.Task[Any]] = {}

    async def detach(self, run: WorkspaceRun) -> None:
        """Called once the short wait elapses without the run reaching a
        terminal status. Schedules a background task that watches the run's
        sidecar handle to completion, persists the real terminal result, then
        — only when run.origin == conversation — dispatches the follow-up
        turn and completion push."""
        if run.id is None:
            log.warning("workspace_run_detach_missing_id", command=run.command)
            return
        task = asyncio.create_task(self._watch_to_terminal(run))
        self._tasks[run.id] = task
        task.add_done_callback(lambda _t, rid=run.id: self._tasks.pop(rid, None))

    async def reattach(self, run: WorkspaceRun) -> None:
        """Startup reconciliation: re-adopts a row with ended_at IS NULL. If
        follow_through_notified is already True on an otherwise-terminal row
        found at startup, this is not double-delivery — it is the one
        delivery that never went out."""
        if run.id is None:
            return
        if run.ended_at is not None:
            if not run.follow_through_notified:
                await self._dispatch(run)
            return
        if not run.sidecar_dispatched:
            # Crashed between insert_in_progress_run and the POST /run call
            # landing — the sidecar never received this id, no call needed.
            completed = await self._store.complete_run(
                run.id,
                status=WorkspaceRunStatus.FAILED,
                error_summary=_NEVER_DISPATCHED_SUMMARY,
            )
            if completed is not None:
                await self._dispatch(completed)
            return
        if self._client is None:
            log.warning("workspace_run_reattach_no_client", run_id=str(run.id))
            return
        status = await self._client.get_run(run.id)
        if status is None:
            # Edge Case 3: computer restarted and lost the in-flight process.
            # Ze does not invent success.
            completed = await self._store.complete_run(
                run.id,
                status=WorkspaceRunStatus.FAILED,
                error_summary=_LOST_ON_RESTART_SUMMARY,
            )
            if completed is not None:
                await self._dispatch(completed)
            return
        if status.status == "running":
            await self.detach(run)
            return
        completed = await self._complete_from_status(run.id, status)
        if completed is not None:
            await self._dispatch(completed)

    async def cancel(self, run_id: UUID) -> WorkspaceRun | None:
        """Administrative stop (User Story 3) — persists status=cancelled directly
        via store.cancel_run (which leaves output_preview/files_touched untouched,
        unlike complete_run) and dispatches follow-through immediately, rather
        than waiting for the watch loop to observe the exit event.

        Returns None if the run was already terminal (already-finished cancel,
        route layer turns this into 409). If a `detach`ed watch task is still
        running for this id, it will see the row already terminal once its own
        completion write lands (complete_run's `WHERE ended_at IS NULL` guard)
        and no-op — this never double-dispatches.
        """
        cancelled = await self._store.cancel_run(run_id)
        if cancelled is None:
            return None
        await self._dispatch(cancelled)
        return cancelled

    async def _watch_to_terminal(self, run: WorkspaceRun) -> None:
        assert run.id is not None
        assert self._client is not None
        try:
            async for event in self._client.watch_run(run.id):
                if event.type == "exit":
                    break
        except Exception as exc:  # sidecar/network failure while detached
            log.warning(
                "workspace_run_watch_failed", run_id=str(run.id), error=str(exc)
            )
            completed = await self._store.complete_run(
                run.id,
                status=WorkspaceRunStatus.FAILED,
                error_summary=str(exc),
            )
            if completed is not None:
                await self._dispatch(completed)
            return

        status = await self._client.get_run(run.id)
        if status is None:
            completed = await self._store.complete_run(
                run.id,
                status=WorkspaceRunStatus.FAILED,
                error_summary=_LOST_ON_RESTART_SUMMARY,
            )
        else:
            completed = await self._complete_from_status(run.id, status)
        if completed is None:
            log.info("workspace_run_already_terminal", run_id=str(run.id))
            return
        await self._dispatch(completed)

    async def _complete_from_status(
        self, run_id: UUID, status: WorkspaceRunStatusDTO
    ) -> WorkspaceRun | None:
        return await self._store.complete_run(
            run_id,
            status=_STATUS_MAP.get(status.status, WorkspaceRunStatus.FAILED),
            exit_code=status.exit_code,
            output_preview=status.stdout_preview or status.stderr_preview or "",
            output_file_path=status.output_file_path,
            files_touched=status.files_touched,
            error_summary=status.stderr_preview if status.exit_code else None,
        )

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
