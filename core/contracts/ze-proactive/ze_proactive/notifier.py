from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone

from ze_agents.interface.base import AppInterface
from ze_agents.interface.types import Action, Notification
from ze_logging import get_logger
from ze_proactive.attention_budget import budget_status
from ze_proactive.errors import BudgetUnavailableError, PushPolicyError
from ze_proactive.governor import decide
from ze_proactive.notification_store import NotificationStore
from ze_proactive.push_kinds import QUIET_HOURS_SUMMARY, registered_push_kinds
from ze_proactive.push_log_store import PushLogStore
from ze_proactive.quiet_hours import InterruptionSettingsStore, is_active
from ze_proactive.types import (
    BudgetStatus,
    NotificationRow,
    OncePer,
    PushKind,
    PushOutcome,
)

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

    async def budget_status(self) -> BudgetStatus:
        if self._push_log is None:
            raise BudgetUnavailableError("notifier has no push log")
        return await budget_status(self._push_log, self._max)

    async def remaining_budget(self) -> int:
        try:
            return (await self.budget_status()).remaining
        except Exception as exc:
            log.warning("attention_budget_check_failed", error=str(exc))
            return self._max

    async def notify(
        self,
        kind: PushKind,
        title: str,
        body: str,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        target_parent_id: str | None = None,
        once_per: OncePer | None = None,
        actions: Sequence[Action] = (),
        format: str = "text",
    ) -> PushOutcome:
        return await self._notify(
            kind,
            kind.urgency,
            title,
            body,
            target_type=target_type,
            target_id=target_id,
            target_parent_id=target_parent_id,
            once_per=once_per,
            actions=actions,
            format=format,
        )

    async def on_cooldown(self, once_per: OncePer) -> bool:
        """Read-only: is `once_per` cooling? False when the store cannot say."""
        if self._push_log is None:
            return False
        try:
            return await self._push_log.is_cooling(once_per)
        except Exception as exc:
            log.warning("push_cooldown_check_failed", key=once_per.key, error=str(exc))
            return False

    async def recent_discretionary_bodies(self, hours: float) -> list[str]:
        """Bodies of the discretionary pushes sent in the window, newest first.
        Empty when the store cannot say."""
        if self._push_log is None:
            return []
        try:
            return await self._push_log.recent_discretionary_payloads(hours)
        except Exception as exc:
            log.warning("push_history_read_failed", error=str(exc))
            return []

    async def _notify(
        self,
        kind: PushKind,
        urgency: str,
        title: str,
        body: str,
        *,
        target_type: str | None,
        target_id: str | None,
        target_parent_id: str | None = None,
        once_per: OncePer | None,
        actions: Sequence[Action],
        format: str,
        ignore_quiet: bool = False,
    ) -> PushOutcome:
        discretionary = kind.push_class == "discretionary"
        if discretionary and once_per is None:
            raise PushPolicyError(
                f"discretionary push {kind.event_type!r} needs a once_per"
            )
        if kind.push_class == "requested" and once_per is not None:
            raise PushPolicyError(
                f"requested push {kind.event_type!r} takes no once_per"
            )
        if self._store is None:
            log.warning("proactive_notify_no_store", event_type=kind.event_type)
            return "failed"

        quiet = (
            False
            if kind.push_class == "requested" or ignore_quiet
            else await self.quiet_now()
        )

        budget_won: bool | None = True if discretionary else None
        claim_id: int | None = None
        if once_per is not None and self._push_log is not None:
            try:
                claim = await self._push_log.claim(
                    event_type=kind.event_type,
                    once_per=once_per,
                    discretionary=discretionary,
                    max_discretionary=self._max,
                    payload=body,
                )
            except Exception as exc:
                log.warning("push_claim_failed", key=once_per.key, error=str(exc))
            else:
                if claim.status == "cooling":
                    log.debug("proactive_notify_deduped", key=once_per.key)
                    return "deduped"
                if claim.status == "over_budget":
                    budget_won = False
                else:
                    claim_id = claim.claim_id

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
                target_parent_id=target_parent_id,
                push_class=kind.push_class,
                urgency=urgency,
                format=format,
                actions=action_dicts,
                delivery=delivery,
            )
        except Exception as exc:
            log.warning("proactive_notify_persist_failed", error=str(exc))
            await self._release(claim_id)
            return "failed"

        if decision != "deliver":
            await self._push_silent(row, body, delivery)
            return "held" if decision == "hold" else "suppressed_budget"

        try:
            await self._deliver(row, body, format, list(actions), buzz=True)
        except Exception as exc:
            log.warning("proactive_push_failed", error=str(exc))
            await self._release(claim_id)
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
            once_per=None,
            actions=(),
            format="text",
            ignore_quiet=True,
        )
        return n

    async def _release(self, claim_id: int | None) -> None:
        if claim_id is not None and self._push_log is not None:
            try:
                await self._push_log.release(claim_id)
            except Exception as exc:
                log.warning("push_claim_release_failed", error=str(exc))

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
            target_parent_id=row.target_parent_id,
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
