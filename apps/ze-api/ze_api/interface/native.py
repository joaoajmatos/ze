from __future__ import annotations

import math
import re
from dataclasses import asdict
from datetime import datetime, timezone
from numbers import Integral, Real
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, ClassVar, Literal
from uuid import UUID, uuid4

from ze_components.summary import describe_components
from ze_agents.interface.types import (
    Action,
    ConfirmationRequest,
    Notification,
    OutboundMessage,
)
from ze_api.api.ws.frames import build_prompt_frame
from ze_core.conversation.messages import Message
from ze_logging import get_logger

if TYPE_CHECKING:
    from ze_notifications.notifier import Notifier as PushNotifier
    from ze_core.conversation.messages import MessageStore
    from ze_api.api.ws.connection import ConnectionManager

log = get_logger(__name__)

_NTFY_PRIORITY_MAP = {"low": 2, "normal": 3, "high": 5}
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_DANGER_LABELS = frozenset({"stop", "cancel", "abandon", "dismiss"})


_ROLLBACK_ENTRY_FIELDS = (
    "entry_id",
    "tool",
    "effect_phrase",
    "outcome",
    "at",
    "failure_code",
)


def _public_trace(data: dict) -> dict:
    """Drop what must stay on the server: owning agent and undo arguments."""
    for call in data.get("tool_calls") or []:
        if isinstance(call, dict):
            call.pop("agent", None)
            call.pop("undo_args", None)
    rollback = data.get("rollback")
    if isinstance(rollback, dict):
        rollback["entries"] = [
            {k: e.get(k) for k in _ROLLBACK_ENTRY_FIELDS}
            for e in rollback.get("entries") or []
            if isinstance(e, dict)
        ]
    return data


def _json_safe(value: Any) -> Any:
    """Coerce a trace payload to strict-JSON types so a frame send cannot raise."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Integral):
        # numpy int scalars reach traces via embedding scores — keep them numeric.
        return int(value)
    if isinstance(value, Real):
        # numpy float scalars (float32/float64) — keep the JSON number, not a string.
        num = float(value)
        return num if math.isfinite(num) else None
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class NativeAppInterface:
    """AppInterface for the web client — WebSocket + ntfy delivery."""

    confirmation_style: ClassVar[Literal["inline", "async"]] = "async"

    def __init__(
        self,
        message_store: MessageStore,
        connection_manager: ConnectionManager,
        notifier: PushNotifier | None,
        quiet_now: Callable[[], Awaitable[bool]] | None = None,
        confirm_frame_for: Callable[[Notification], Awaitable[dict | None]]
        | None = None,
    ) -> None:
        self._store = message_store
        self._conn = connection_manager
        self._notifier = notifier
        self._quiet_now = quiet_now
        # A push that stands for an open confirmation (a held write) also sends
        # its card, the same frame the on-connect replay sends.
        self._confirm_frame_for = confirm_frame_for

    async def _is_quiet(self) -> bool:
        if self._quiet_now is None:
            return False
        try:
            return await self._quiet_now()
        except Exception as exc:
            log.warning("native_interface_quiet_check_failed", error=str(exc))
            return False

    async def send(self, message: OutboundMessage) -> None:
        await self._send_message(message.content)

    async def push(self, notification: Notification) -> None:
        # The governor already decided whether this push may interrupt, so the
        # quiet-hours check is not repeated here.
        if notification.delivery in {"held", "suppressed"}:
            if notification.event_type is not None:
                await self._send_notification_frame(notification)
            return
        if not notification.in_chat:
            await self._ntfy(
                notification.content,
                _NTFY_PRIORITY_MAP.get(notification.urgency, 3),
                buzz=notification.buzz,
                respect_quiet=False,
            )
            if notification.event_type is not None:
                await self._send_notification_frame(notification)
            await self._send_confirm_card(notification)
            return
        await self._send_message(
            notification.content,
            ntfy_priority=_NTFY_PRIORITY_MAP.get(notification.urgency, 3),
            buzz=notification.buzz,
            respect_quiet=False,
        )
        if notification.actions:
            await self._send_action_request(notification)
        if notification.event_type is not None:
            await self._send_notification_frame(notification)

    async def send_trace_partial(
        self, message_id: str, fields: dict, thread_id: str | None = None
    ) -> None:
        try:
            await self._conn.send_frame(
                {
                    "type": "trace_update",
                    "message_id": message_id,
                    "partial": True,
                    "agent": "",
                    "routing_method": "",
                    "confidence": 0.0,
                    "score_gap": 0.0,
                    "is_compound": False,
                    "subtasks": [],
                    "memory_chunks": [],
                    "tool_calls": [],
                    "total_duration_ms": 0,
                    **fields,
                },
                thread_id,
            )
        except Exception as exc:
            log.warning("native_interface_trace_partial_failed", error=str(exc))

    async def _send_message(
        self,
        text: str,
        thread_id: str | None = None,
        components: list[dict] | None = None,
        ntfy_priority: int = 3,
        trace: Any | None = None,
        message_id: str | None = None,
        replaces: UUID | None = None,
        after_save: Callable[[], Awaitable[bool]] | None = None,
        buzz: bool = True,
        respect_quiet: bool = True,
    ) -> bool:
        msg = Message(
            id=UUID(message_id) if message_id else uuid4(),
            role="assistant",
            text=text,
            components=components or [],
            read=False,
            created_at=datetime.now(timezone.utc),
            thread_id=thread_id,
            replaces=replaces,
        )
        try:
            await self._store.save(msg)
        except Exception as exc:
            log.warning("native_interface_save_failed", error=str(exc))

        if trace is not None:
            try:
                await self._store.save_trace(msg.id, trace)
            except Exception as exc:
                log.warning("native_interface_save_trace_failed", error=str(exc))

        if after_save is not None and not await after_save():
            # The reply is stored but must not be shown (a retry that could not
            # supersede its original).
            return False

        if trace is not None:
            try:
                await self._conn.send_frame(
                    {
                        "type": "trace_update",
                        "message_id": str(msg.id),
                        **_public_trace(_json_safe(asdict(trace))),
                    },
                    thread_id,
                )
            except Exception as exc:
                log.warning("native_interface_trace_update_failed", error=str(exc))

        try:
            await self._conn.push(msg, thread_id)
        except Exception as exc:
            log.warning("native_interface_push_failed", error=str(exc))

        await self._ntfy(
            text or describe_components(components) or "Ze sent you something.",
            ntfy_priority,
            buzz=buzz,
            respect_quiet=respect_quiet,
        )
        return True

    async def _ntfy(
        self, text: str, priority: int, *, buzz: bool, respect_quiet: bool
    ) -> None:
        # Only push via ntfy when the WebSocket is not connected — the client is
        # receiving frames in real-time when connected, so a push notification
        # would be redundant noise.
        if (
            buzz
            and self._notifier is not None
            and not self._conn.connected
            and not (respect_quiet and await self._is_quiet())
        ):
            from ze_notifications.types import Notification as PushNotification

            try:
                await self._notifier.push(
                    PushNotification(title="Ze", body=text[:200], priority=priority)
                )
            except Exception as exc:
                log.warning("native_interface_ntfy_failed", error=str(exc))

    async def send_with_thread(
        self,
        text: str,
        thread_id: str | None,
        components: list[dict] | None = None,
        trace: Any | None = None,
        message_id: str | None = None,
        replaces: UUID | None = None,
        after_save: Callable[[], Awaitable[bool]] | None = None,
    ) -> bool:
        """Called by the WS handler after graph invocation to attach the thread_id.

        `after_save` runs once the reply is stored and before any frame goes out;
        returning False suppresses delivery and makes this return False.
        """
        return await self._send_message(
            text,
            thread_id=thread_id,
            components=components,
            trace=trace,
            message_id=message_id,
            replaces=replaces,
            after_save=after_save,
        )

    async def send_confirmation(self, request: ConfirmationRequest) -> None:
        """Deliver a confirmation UI frame over WebSocket (and ntfy if backgrounded)."""
        await self._conn.send_frame(
            build_prompt_frame(
                request_id=str(uuid4()),
                thread_id=None,
                title=request.content,
                actions=_confirmation_actions(request.options),
            )
        )

        if (
            self._notifier is not None
            and not self._conn.connected
            and not await self._is_quiet()
        ):
            from ze_notifications.types import Notification as PushNotification

            body = (
                f"Ze needs your approval:\n{request.content}"
                if request.content
                else "Ze needs your approval."
            )
            try:
                await self._notifier.push(
                    PushNotification(title="Ze", body=body[:200], priority=5)
                )
            except Exception as exc:
                log.warning("native_interface_confirmation_ntfy_failed", error=str(exc))

    async def _send_confirm_card(self, notification: Notification) -> None:
        if self._confirm_frame_for is None:
            return
        try:
            frame = await self._confirm_frame_for(notification)
            if frame is not None:
                await self._conn.send_frame(frame)
        except Exception as exc:
            log.warning("native_interface_confirm_card_failed", error=str(exc))

    async def _send_notification_frame(self, notification: Notification) -> None:
        try:
            await self._conn.send_frame(
                {
                    "type": "notification",
                    "id": notification.id,
                    "event_type": notification.event_type,
                    "source": notification.source,
                    "title": notification.title,
                    "body": notification.content,
                    "target_type": notification.target_type,
                    "target_id": notification.target_id,
                    "target_parent_id": notification.target_parent_id,
                    "created_at": notification.created_at.isoformat()
                    if notification.created_at
                    else None,
                    "read": False,
                    "push_class": notification.push_class,
                    "urgency": notification.urgency,
                    "delivery": notification.delivery,
                }
            )
        except Exception as exc:
            log.warning("native_interface_notification_frame_failed", error=str(exc))

    async def _send_action_request(self, notification: Notification) -> None:
        prompt = (
            _strip_html(notification.content)
            if notification.format == "html"
            else notification.content
        )
        await self._conn.send_frame(
            build_prompt_frame(
                request_id=str(uuid4()),
                thread_id=None,
                title=prompt,
                actions=[_action_to_frame(action) for action in notification.actions],
            )
        )


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text).strip()


def _action_to_frame(action: Action) -> dict[str, str]:
    label_key = action.label.lower()
    if any(word in label_key for word in _DANGER_LABELS):
        style = "danger"
    elif action.row == 0:
        style = "primary"
    else:
        style = "secondary"
    return {"label": action.label, "value": action.payload, "style": style}


def _confirmation_actions(options: list[str]) -> list[dict[str, str]]:
    if options == ["Approve", "Cancel"]:
        return [
            {"label": "Approve", "value": "approve", "style": "primary"},
            {"label": "Cancel", "value": "deny", "style": "secondary"},
        ]
    return [{"label": opt, "value": opt.lower()} for opt in options]
