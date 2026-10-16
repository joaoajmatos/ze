"""Open, answer and resume held writes (Phase 181, FR-025).

An unattended run (workflow step, goal milestone) that reaches an asks-first call the
plan did not pre-approve stops and leaves a `held_writes` row. This module owns the
two halves: `open_hold` records the stop and sends the one push; `HeldWriteResumer`
claims the user's answer exactly once and continues the run.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import uuid4

from ze_agents.errors import ZeError
from ze_agents.effects import effect_imperative
from ze_agents.park import (
    ConfirmItem,
    ParkedLoop,
    WriteConfirmation,
    WriteDecision,
)
from ze_automation.holds.store import HeldWriteStore
from ze_automation.holds.types import HeldWrite, HeldWriteStatus
from ze_automation.push_kinds import WRITE_APPROVAL_HELD
from ze_logging import get_logger

log = get_logger(__name__)

HELD_TTL = timedelta(hours=24)
HELD_TARGET_TYPE = "held_write"

CHOICE_STATUS: dict[str, HeldWriteStatus] = {
    "approve": HeldWriteStatus.APPROVED,
    "deny": HeldWriteStatus.DENIED,
    "timeout": HeldWriteStatus.EXPIRED,
}


class HeldWriteNotFoundError(ZeError):
    """No held write has this request id."""


class HeldWriteNotOpenError(ZeError):
    """The held write was already decided or expired."""


class HeldWriteEditError(ZeError):
    """An edit names an item that has no editable field."""


class Notify(Protocol):
    async def __call__(
        self, kind: Any, title: str, body: str, **kwargs: Any
    ) -> Any: ...


ResumeRun = Callable[[HeldWrite, str, dict[str, str]], Awaitable[None]]


def confirmation_from_loop(loop: ParkedLoop, round_: int = 1) -> WriteConfirmation:
    """The held-write confirmation for a loop that parked, items in model order."""
    items = [
        ConfirmItem(
            item_id=pw.item_id,
            agent=pw.agent,
            tool=pw.tool,
            effect_phrase=effect_imperative(pw.effect_phrase),
            summary=pw.summary,
            editable_field=pw.editable_field,
            proposed_text=(
                str(pw.args.get(pw.editable_field))
                if pw.editable_field and pw.args.get(pw.editable_field) is not None
                else None
            ),
            conflict=pw.conflict,
        )
        for pw in loop.all_parked()
    ]
    return WriteConfirmation(
        request_id=str(uuid4()), kind="held", round=round_, items=items
    )


def decisions_for(
    hold: HeldWrite, choice: str, edits: dict[str, str]
) -> dict[str, WriteDecision]:
    """Per-item decisions for a held write answered with `choice`."""
    decisions: dict[str, WriteDecision] = {}
    for item in hold.items:
        item_id = item["item_id"]
        if choice == "approve":
            text = edits.get(item_id)
            if text is not None and item.get("editable_field"):
                decisions[item_id] = WriteDecision(item_id, "edited", str(text))
            else:
                decisions[item_id] = WriteDecision(item_id, "approved")
        elif choice == "timeout":
            decisions[item_id] = WriteDecision(item_id, "timed_out")
        else:
            decisions[item_id] = WriteDecision(item_id, "denied")
    return decisions


async def open_hold(
    *,
    held_store: HeldWriteStore,
    notify: Notify,
    source: str,
    owner_ref: str,
    source_name: str,
    confirmation: WriteConfirmation,
    payload: dict[str, Any],
    now: datetime | None = None,
) -> HeldWrite:
    """Record a held run and send the one push asking the user."""
    created = now or datetime.now(tz=timezone.utc)
    hold = HeldWrite(
        request_id=confirmation.request_id,
        source=source,
        owner_ref=owner_ref,
        items=[asdict(item) for item in confirmation.items],
        payload={**payload, "source_name": source_name},
        expires_at=created + HELD_TTL,
    )
    await held_store.create(hold)
    first = confirmation.items[0] if confirmation.items else None
    body = (
        f"{first.effect_phrase}: {first.summary}" if first else "A step needs approval"
    )
    if len(confirmation.items) > 1:
        body += f" (+{len(confirmation.items) - 1} more)"
    try:
        await notify(
            WRITE_APPROVAL_HELD,
            f"{source.capitalize()} '{source_name}' needs your OK",
            body[:200],
            target_type=HELD_TARGET_TYPE,
            target_id=hold.request_id,
        )
    except Exception as exc:
        log.warning(
            "held_write_push_failed", request_id=hold.request_id, error=str(exc)
        )
    log.info(
        "held_write_opened",
        request_id=hold.request_id,
        source=source,
        owner_ref=owner_ref,
        items=len(hold.items),
    )
    return hold


class HeldWriteResumer:
    """Claims an answer to a held write once, then continues the held run."""

    def __init__(
        self,
        held_store: HeldWriteStore,
        resume_workflow: ResumeRun | None = None,
        resume_goal: ResumeRun | None = None,
    ) -> None:
        self._store = held_store
        self._resume_workflow = resume_workflow
        self._resume_goal = resume_goal
        self._tasks: set[asyncio.Task] = set()

    def configure(
        self,
        *,
        resume_workflow: ResumeRun | None = None,
        resume_goal: ResumeRun | None = None,
    ) -> None:
        if resume_workflow is not None:
            self._resume_workflow = resume_workflow
        if resume_goal is not None:
            self._resume_goal = resume_goal

    async def decide(
        self, request_id: str, choice: str, edits: dict[str, str] | None = None
    ) -> HeldWrite:
        """Claim the answer. Raises when the hold is unknown, closed or the edit is invalid."""
        hold = await self._store.get(request_id)
        if hold is None:
            raise HeldWriteNotFoundError(request_id)
        if hold.status is not HeldWriteStatus.OPEN:
            raise HeldWriteNotOpenError(request_id)
        editable = {
            item["item_id"] for item in hold.items if item.get("editable_field")
        }
        for item_id in edits or {}:
            if item_id not in editable:
                raise HeldWriteEditError(item_id)
        if not await self._store.decide(request_id, CHOICE_STATUS[choice]):
            raise HeldWriteNotOpenError(request_id)
        hold.status = CHOICE_STATUS[choice]
        return hold

    async def run(
        self, hold: HeldWrite, choice: str, edits: dict[str, str] | None = None
    ) -> None:
        runner = (
            self._resume_workflow if hold.source == "workflow" else self._resume_goal
        )
        if runner is None:
            log.error(
                "held_write_no_resumer", request_id=hold.request_id, source=hold.source
            )
            return
        try:
            await runner(hold, choice, dict(edits or {}))
        except Exception as exc:
            log.exception(
                "held_write_resume_failed", request_id=hold.request_id, error=str(exc)
            )

    async def resume(
        self, request_id: str, choice: str, edits: dict[str, str] | None = None
    ) -> HeldWrite:
        hold = await self.decide(request_id, choice, edits)
        await self.run(hold, choice, edits)
        return hold

    def resume_in_background(
        self, hold: HeldWrite, choice: str, edits: dict | None
    ) -> None:
        task = asyncio.create_task(self.run(hold, choice, edits))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
