from __future__ import annotations

from datetime import datetime, timezone

from ze_communication.types import SentMessage
from ze_logging import get_logger
from ze_sdk.contribution import (
    ActionLifecycle,
    ActionOutcome,
    ActionRecord,
    ActionRecorder,
    ActionRecordStore,
)

from ze_messenger.outbound.store import OutboundSendStore
from ze_messenger.outbound.types import OutboundSend, OutboundSendOutcome

log = get_logger(__name__)

_OUTCOME_MAP = {
    OutboundSendOutcome.SUCCESS: (ActionLifecycle.SUCCEEDED, ActionOutcome.SUCCESS, None),
    OutboundSendOutcome.FAILURE: (
        ActionLifecycle.FAILED,
        ActionOutcome.FAILURE,
        "send_failed",
    ),
    OutboundSendOutcome.UNKNOWN: (
        ActionLifecycle.UNKNOWN,
        ActionOutcome.UNKNOWN,
        "outcome_unobserved",
    ),
}

_outbound_store: OutboundSendStore | None = None
_action_store: ActionRecordStore | None = None


def configure_outbound_ledger(
    *,
    outbound_store: OutboundSendStore | None,
    action_record_store: ActionRecordStore | None,
) -> None:
    global _outbound_store, _action_store
    _outbound_store = outbound_store
    _action_store = action_record_store


async def persist_outbound_send(
    *,
    sent: SentMessage | None,
    channel_id: str,
    outcome: OutboundSendOutcome,
    failure_code: str | None = None,
) -> OutboundSend | None:
    if _outbound_store is None:
        return None
    now = datetime.now(timezone.utc)
    send = OutboundSend(
        message_id="" if sent is None else sent.message_id,
        thread_id="" if sent is None else sent.thread_id,
        channel_type="email" if sent is None else sent.channel_type.value,
        channel_id=channel_id,
        sent_at=now if sent is None else sent.sent_at,
        outcome=outcome,
        failure_code=failure_code,
    )
    return await _outbound_store.insert(send)


async def record_outbound_message(send: OutboundSend) -> ActionRecord | None:
    if _action_store is None or send.id is None:
        return None
    lifecycle, outcome, failure_code = _OUTCOME_MAP[send.outcome]
    if send.failure_code:
        failure_code = send.failure_code
    recorder = ActionRecorder(_action_store)
    key_lifecycle = lifecycle
    try:
        record = await recorder.record_action(
            producer_kind="messenger",
            source_record_type="outbound",
            source_record_id=str(send.id),
            action_kind="send_email",
            lifecycle=key_lifecycle,
            outcome=outcome,
            actor="messenger",
            producer_plugin="ze-messenger",
            occurred_at=send.sent_at,
            summary=f"outbound email {send.outcome.value}",
            failure_code=failure_code,
        )
    except Exception as exc:
        log.warning(
            "action_record_delivery_failed",
            producer_plugin="ze-messenger",
            authoritative_record_id=str(send.id),
            error=type(exc).__name__,
        )
        if _outbound_store is not None:
            await _outbound_store.mark_ledger_handoff(
                send.id, key=str(send.id), pending=True
            )
        return None
    if _outbound_store is not None:
        await _outbound_store.mark_ledger_handoff(
            send.id, key=str(send.id), pending=False
        )
    log.info(
        "action_record_delivered",
        producer_plugin="ze-messenger",
        record_id=str(getattr(record, "id", record)),
    )
    return record
