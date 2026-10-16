from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID

from ze_agents.registry import get_agent
from ze_agents.rollback import RollbackScope, is_error_result, rollback_scope
from ze_core.conversation.messages.store import MessageStore
from ze_core.conversation.messages.types import RollbackEntry, RollbackRecord
from ze_core.conversation.retry import UndoPlanEntry
from ze_logging import get_logger

log = get_logger(__name__)

_MAX_FAILURE_CODE = 120


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _code(text: object) -> str:
    return str(text)[:_MAX_FAILURE_CODE]


async def run_rollback(
    plan: list[UndoPlanEntry],
    *,
    message_id: UUID,
    thread_id: str,
    session_id: str,
    message_store: MessageStore,
) -> RollbackRecord:
    """Run each undo through its owning agent, in plan order, stopping at the first failure.

    The executor never calls a model. The record is stored after every entry, so a crash
    leaves an honest account of what was undone. A full success returns state
    `rolled_back_retry_failed`: nothing has been regenerated yet, and the caller moves
    the state on.
    """
    started_at = _now()
    entries = [
        RollbackEntry(
            entry_id=e.entry_id,
            call_index=e.call_index,
            tool=e.tool,
            undo_tool=e.undo_tool,
            effect_phrase=e.effect_phrase,
            outcome="not_attempted",
        )
        for e in plan
    ]

    def _record(state: str) -> RollbackRecord:
        return RollbackRecord(
            state=state,  # type: ignore[arg-type]
            entries=list(entries),
            started_at=started_at,
            updated_at=_now(),
        )

    for index, step in enumerate(plan):
        failure = await _run_one(step, message_id=message_id, session_id=session_id)
        entries[index] = replace(
            entries[index],
            outcome="undone" if failure is None else "failed",
            at=_now(),
            failure_code=failure,
        )
        done = failure is None and index == len(plan) - 1
        record = _record("rolled_back_retry_failed" if done else "partial")
        await message_store.set_rollback(message_id, record)
        if failure is not None:
            log.warning(
                "rollback_undo_failed",
                thread_id=thread_id,
                tool=step.tool,
                undo_tool=step.undo_tool,
                failure_code=failure,
            )
            return record
        log.info(
            "rollback_undone",
            thread_id=thread_id,
            tool=step.tool,
            undo_tool=step.undo_tool,
        )
    return _record("rolled_back_retry_failed")


async def _run_one(
    step: UndoPlanEntry, *, message_id: UUID, session_id: str
) -> str | None:
    """None on success, else a sanitized failure code."""
    try:
        agent = get_agent(step.agent)
    except Exception as exc:
        return type(exc).__name__
    try:
        with rollback_scope(RollbackScope(retried_message_id=message_id)):
            call = await agent.run_undo(
                step.undo_tool, step.undo_args, session_id=session_id
            )
    except Exception as exc:
        return type(exc).__name__
    if not call.success:
        return _code(call.error or "undo_failed")
    if is_error_result(call.result):
        error = call.result.get("error") if isinstance(call.result, dict) else None
        return _code(error or "undo_returned_error")
    return None
