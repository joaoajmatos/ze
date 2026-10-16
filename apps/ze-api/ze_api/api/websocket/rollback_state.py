"""Shared Retry rollback bookkeeping for the retry handler and confirmation resume."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from ze_api.api.websocket.connection import ConnectionManager
from ze_api.api.schemas import RollbackRecordResponse
from ze_core.conversation.messages.types import (
    RollbackRecord,
    RollbackState,
    RollbackTrace,
)
from ze_logging import get_logger

log = get_logger(__name__)


def retry_replaces_of(config: dict | None) -> UUID | None:
    """The message a paused retry will replace, from its graph config."""
    raw = ((config or {}).get("configurable") or {}).get("retry_replaces")
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        return None


def undone_phrases(record: RollbackRecord | None) -> list[str]:
    if record is None:
        return []
    return [e.effect_phrase for e in record.entries if e.outcome == "undone"]


def _join(phrases: list[str]) -> str:
    if len(phrases) <= 1:
        return "".join(phrases)
    return ", ".join(phrases[:-1]) + f" and {phrases[-1]}"


def rollback_notice(record: RollbackRecord | None) -> str:
    """One honest sentence about what a Retry changed; used when it did not finish."""
    done = undone_phrases(record)
    failed = next(
        (e for e in (record.entries if record else []) if e.outcome == "failed"), None
    )
    if failed is not None:
        if done:
            return (
                f"Ze undid {_join(done)}, but could not undo {failed.effect_phrase}. "
                "The rest of the reply stands."
            )
        return f"Ze could not undo {failed.effect_phrase}. Nothing was changed."
    if done:
        return f"Ze undid {_join(done)}, but could not write a new reply."
    return "Retry failed. The original reply is unchanged."


async def publish_rollback(
    conn_mgr: ConnectionManager,
    thread_id: str,
    message_id: UUID,
    record: RollbackRecord,
) -> None:
    public = public_rollback_record(record)
    await conn_mgr.send_frame(
        {
            "type": "message_rollback",
            "message_id": str(message_id),
            "thread_id": thread_id,
            "rollback": public,
        },
        thread_id,
    )


def public_rollback_record(record: RollbackRecord) -> dict[str, Any]:
    return RollbackRecordResponse.model_validate(record).model_dump(mode="json")


async def move_rollback(
    msg_store: Any,
    conn_mgr: ConnectionManager,
    thread_id: str,
    message_id: UUID,
    state: RollbackState,
    *,
    record: RollbackRecord | None = None,
    replaced_by: UUID | None = None,
) -> RollbackRecord | None:
    """Set the stored rollback state and tell the client. No record, no change."""
    if record is None:
        message = await msg_store.get_message(message_id)
        record = message.rollback if message is not None else None
    if record is None:
        return None
    moved = replace(
        record,
        state=state,
        updated_at=datetime.now(timezone.utc).isoformat(),
        replaced_by=str(replaced_by) if replaced_by is not None else record.replaced_by,
    )
    await msg_store.set_rollback(message_id, moved)
    try:
        await publish_rollback(conn_mgr, thread_id, message_id, moved)
    except Exception as exc:
        log.warning("ws_rollback_frame_failed", error=str(exc))
    return moved


async def deliver_retry_reply(
    container: Any,
    msg_store: Any,
    conn_mgr: ConnectionManager,
    *,
    thread_id: str,
    old_id: UUID,
    outcome: Any,
    record: RollbackRecord | None,
    components: list[dict] | None = None,
) -> bool:
    """Store the retry's reply, supersede the original, then announce both.

    The client never sees a reply that failed to replace the original.
    """
    new_id = UUID(outcome.message_id) if outcome.message_id else uuid4()
    trace = outcome.final_state.get("message_trace")
    undone = [e for e in (record.entries if record else []) if e.outcome == "undone"]
    if trace is not None and undone:
        trace.rollback = RollbackTrace(replaces=str(old_id), entries=undone)

    async def _supersede() -> bool:
        linked = await msg_store.mark_superseded(old_id, new_id)
        if linked and record is not None:
            await msg_store.set_rollback(
                old_id,
                replace(
                    record,
                    state="superseded",
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    replaced_by=str(new_id),
                ),
            )
        return linked

    delivered = await container.interface.send_with_thread(
        outcome.response,
        thread_id=thread_id,
        components=components
        if components is not None
        else (outcome.final_state.get("components") or None),
        trace=trace,
        message_id=str(new_id),
        replaces=old_id,
        after_save=_supersede,
    )
    if not delivered:
        log.warning("ws_retry_supersede_failed", old=str(old_id), new=str(new_id))
        return False
    await conn_mgr.send_frame(
        {
            "type": "message_superseded",
            "message_id": str(old_id),
            "replaced_by": str(new_id),
        },
        thread_id,
    )
    if record is not None:
        final = replace(record, state="superseded", replaced_by=str(new_id))
        try:
            await publish_rollback(conn_mgr, thread_id, old_id, final)
        except Exception as exc:
            log.warning("ws_rollback_frame_failed", error=str(exc))
    return True
