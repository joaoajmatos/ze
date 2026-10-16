from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone

from ze_agents.interface.base import AppInterface
from ze_agents.interface.types import Action, Notification
from ze_logging import get_logger
from ze_proactive.attention_budget import (
    ATTENTION_PUSH_EVENT_KEY,
    release_shared,
    try_claim_shared,
    within_budget,
)
from ze_proactive.errors import PushPolicyError
from ze_proactive.governor import decide
from ze_proactive.notification_store import NotificationStore
from ze_proactive.push_kinds import QUIET_HOURS_SUMMARY, registered_push_kinds
from ze_proactive.push_log_store import PushLogStore
from ze_proactive.quiet_hours import InterruptionSettingsStore, is_active
from ze_proactive.types import NotificationRow, PushKind, PushOutcome

log = get_logger(__name__)

_MAX_CONTENT_LEN = 4096
_URGENCY_RANK = {"high": 0, "normal": 1, "low": 2}


class ProactiveNotifier:
    """The one send path for proactive pushes. Every push is classified by its
    `PushKind`; the governor decides deliver / hold / suppress."""

    def __init__(
        self,
        interface: AppInterface,
        notification_store: NotificationStore | None,
        *,
        push_log: PushLogStore | None = None,
        settings_store: InterruptionSettingsStore | None = None,
        max_discretionary_per_day: int = 5,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._interface = interface
        self._store = notification_store
        self._push_log = push_log
        self._settings = settings_store
        self._max = max_discretionary_per_day
        self._clock = clock

    @property
    def max_discretionary_per_day(self) -> int:
        return self._max

    async def quiet_now(self) -> bool:
        if self._settings is None:
            return False
        try:
            return is_active(await self._settings.get(), self._clock())
        except Exception as exc:
            log.warning("quiet_hours_check_failed", error=str(exc))
            return False

    async def remaining_budget(self) -> int:
        if self._push_log is None:
            return self._max
        try:
            used = await self._push_log.count_sent_within_hours(
                ATTENTION_PUSH_EVENT_KEY, 24.0
            )
        except Exception as exc:
            log.warning("attention_budget_check_failed", error=str(exc))
            return self._max
        return max(0, self._max - used)

    async def notify(
        self,
        kind: PushKind,
        title: str,
        body: str,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        budget_key: str | None = None,
        actions: Sequence[Action] = (),
        format: str = "text",
        dedup_hours: float | None = None,
    ) -> PushOutcome:
        return await self._notify(
            kind,
            kind.urgency,
            title,
            body,
            target_type=target_type,
            target_id=target_id,
            budget_key=budget_key,
            actions=actions,
            format=format,
            dedup_hours=dedup_hours,
        )

    async def _notify(
        self,
        kind: PushKind,
        urgency: str,
        title: str,
        body: str,
        *,
        target_type: str | None,
        target_id: str | None,
        budget_key: str | None,
        actions: Sequence[Action],
        format: str,
        dedup_hours: float | None,
        ignore_quiet: bool = False,
    ) -> PushOutcome:
        discretionary = kind.push_class == "discretionary"
        if discretionary and not budget_key:
            raise PushPolicyError(
                f"discretionary push {kind.event_type!r} needs a budget_key"
            )
        if self._store is None:
            log.warning("proactive_notify_no_store", event_type=kind.event_type)
            return "failed"

        if dedup_hours is not None:
            if await self._store.exists_recent(
                event_type=kind.event_type,
                target_type=target_type,
                target_id=target_id,
                hours=dedup_hours,
            ):
                log.debug("proactive_notify_deduped", event_type=kind.event_type)
                return "deduped"

        quiet = (
            False
            if kind.push_class == "requested" or ignore_quiet
            else await self.quiet_now()
        )

        budget_won: bool | None = None
        claimed = False
        if discretionary and self._push_log is not None:
            assert budget_key is not None
            try:
                claimed = await try_claim_shared(
                    self._push_log, budget_key, self._max, payload=title
                )
                if claimed:
                    budget_won = True
                elif await within_budget(self._push_log, self._max):
                    log.debug("proactive_notify_duplicate", key=budget_key)
                    return "duplicate"
                else:
                    budget_won = False
            except Exception as exc:
                log.warning("attention_claim_failed", key=budget_key, error=str(exc))
                budget_won = True
        elif discretionary:
            budget_won = True

        decision = decide(kind, quiet_now=quiet, budget_won=budget_won)
        delivery = {"deliver": "delivered", "hold": "held", "suppress": "suppressed"}[
            decision
        ]
        action_dicts = [
            {"label": a.label, "payload": a.payload, "row": a.row} for a in actions
        ]
        try:
            row = await self._store.create(
                event_type=kind.event_type,
                source=kind.source,
                title=title,
                body=body,
                target_type=target_type,
                target_id=target_id,
                push_class=kind.push_class,
                urgency=urgency,
                format=format,
                actions=action_dicts,
                delivery=delivery,
            )
        except Exception as exc:
            log.warning("proactive_notify_persist_failed", error=str(exc))
            await self._release(claimed, budget_key)
            return "failed"

        if decision != "deliver":
            await self._push_silent(row, body, delivery)
            return "held" if decision == "hold" else "suppressed_budget"

        try:
            await self._deliver(row, body, format, list(actions), buzz=True)
        except Exception as exc:
            log.warning("proactive_push_failed", error=str(exc))
            await self._release(claimed, budget_key)
            try:
                await self._store.mark_failed(row.id)
            except Exception as mark_exc:
                log.warning("proactive_mark_failed_error", error=str(mark_exc))
            return "failed"
        return "delivered"

    async def deliver_held(self) -> int:
        if self._store is None or await self.quiet_now():
            return 0
        held = await self._store.list_held()
        if not held:
            return 0
        released: list[NotificationRow] = []
        for row in held:
            try:
                await self._deliver(
                    row,
                    row.body,
                    row.format,
                    [
                        Action(a["label"], a["payload"], a.get("row", 0))
                        for a in row.actions or []
                    ],
                    buzz=False,
                    delivery="released",
                )
                await self._store.mark_released(row.id)
                released.append(row)
            except Exception as exc:
                log.warning("proactive_release_failed", id=row.id, error=str(exc))
                try:
                    await self._store.mark_failed(row.id)
                except Exception as mark_exc:
                    log.warning("proactive_mark_failed_error", error=str(mark_exc))
        if not released:
            return 0
        top = min((r.urgency for r in released), key=lambda u: _URGENCY_RANK[u])
        n = len(released)
        await self._notify(
            QUIET_HOURS_SUMMARY,
            top,
            "Quiet hours summary",
            f"While quiet hours were on, I held {n} update{'s' if n != 1 else ''}.",
            target_type=None,
            target_id=None,
            budget_key=None,
            actions=(),
            format="text",
            dedup_hours=None,
            ignore_quiet=True,
        )
        return n

    async def _release(self, claimed: bool, budget_key: str | None) -> None:
        if claimed and budget_key is not None and self._push_log is not None:
            try:
                await release_shared(self._push_log, budget_key)
            except Exception as exc:
                log.warning("attention_release_failed", error=str(exc))

    async def _push_silent(
        self, row: NotificationRow, body: str, delivery: str
    ) -> None:
        try:
            await self._interface.push(
                self._frame(row, body, row.format, [], buzz=False, delivery=delivery)
            )
        except Exception as exc:
            log.warning("proactive_push_failed", error=str(exc))

    async def _deliver(
        self,
        row: NotificationRow,
        body: str,
        format: str,
        actions: list[Action],
        *,
        buzz: bool,
        delivery: str = "delivered",
    ) -> None:
        kind = registered_push_kinds().get(row.event_type)
        in_chat = kind.in_chat if kind is not None else True
        chunks = _split(body)
        for i, chunk in enumerate(chunks):
            last = i == len(chunks) - 1
            if i == 0:
                n = self._frame(
                    row,
                    chunk,
                    format,
                    actions if last else [],
                    buzz=buzz,
                    delivery=delivery,
                )
            else:
                n = Notification(
                    content=chunk,
                    format=format,
                    urgency=row.urgency,  # type: ignore[arg-type]
                    actions=actions if last else [],
                    buzz=buzz,
                )
            n.in_chat = in_chat
            await self._interface.push(n)

    @staticmethod
    def _frame(
        row: NotificationRow,
        content: str,
        format: str,
        actions: list[Action],
        *,
        buzz: bool,
        delivery: str,
    ) -> Notification:
        return Notification(
            content=content,
            format=format,
            urgency=row.urgency,  # type: ignore[arg-type]
            actions=actions,
            id=row.id,
            event_type=row.event_type,
            source=row.source,
            title=row.title,
            target_type=row.target_type,
            target_id=row.target_id,
            created_at=row.created_at,
            buzz=buzz,
            push_class=row.push_class,
            delivery=delivery,
        )


def _split(text: str, limit: int = _MAX_CONTENT_LEN) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks
