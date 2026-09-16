from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Any, Callable
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ze_agents.errors import HookAbort
from ze_agents.hooks import BaseHarnessHook, ToolStartEvent
from ze_agents.interrupt import tool_interrupt_fn
from ze_agents.tool import get_tool
from ze_logging import get_logger

log = get_logger(__name__)

_CTX_CACHE_ATTR = "_constraint_veto_facts"

_EMAIL_TOKENS = frozenset(
    {"email", "e-mail", "mail", "gmail", "inbox", "message", "messaging"}
)
_CALENDAR_TOKENS = frozenset(
    {"calendar", "schedule", "scheduling", "meeting", "event", "appointment"}
)
_REMINDER_TOKENS = frozenset({"reminder", "remind", "alarm", "ping"})

KIND_OUTBOUND_DRAFT = "outbound_draft"


class VetoDecision(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    REFUSE = "refuse"


@dataclass
class ConstraintWriteView:
    tool_name: str
    kind: str
    channel: str | None = None
    parties: list[str] = field(default_factory=list)
    when: datetime | None = None
    summary: str = ""


@dataclass
class ReviewedConstraint:
    id: UUID | str
    value: str


def veto_payload(
    constraint_ids: list[str],
    error: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "veto": True,
        "constraint_ids": constraint_ids,
        "error": error,
    }


def default_describe(tool_name: str, args: dict[str, Any]) -> ConstraintWriteView:
    parties = [
        str(args[key]) for key in ("to", "attendee", "name", "contact") if args.get(key)
    ]
    when = _coerce_when(args.get("when") or args.get("start") or args.get("fire_at"))
    return ConstraintWriteView(
        tool_name=tool_name,
        kind=tool_name,
        channel=None,
        parties=parties,
        when=when,
        summary=str({k: v for k, v in args.items() if k not in {"credentials"}}),
    )


def view_from_describe(
    tool_name: str,
    args: dict[str, Any],
    describe: Callable[[dict[str, Any]], Any] | None,
) -> ConstraintWriteView:
    if describe is None:
        return default_describe(tool_name, args)
    raw = describe(args)
    if isinstance(raw, ConstraintWriteView):
        if not raw.tool_name:
            raw.tool_name = tool_name
        return raw
    if isinstance(raw, dict):
        when = raw.get("when")
        if not isinstance(when, datetime):
            when = _coerce_when(when)
        parties = raw.get("parties") or []
        return ConstraintWriteView(
            tool_name=str(raw.get("tool_name") or tool_name),
            kind=str(raw.get("kind") or tool_name),
            channel=raw.get("channel"),
            parties=[str(p) for p in parties if p],
            when=when,
            summary=str(raw.get("summary") or ""),
        )
    return default_describe(tool_name, args)


def match_constraints(
    view: ConstraintWriteView,
    facts: list[ReviewedConstraint],
    *,
    user_timezone: str,
    now: datetime | None = None,
) -> tuple[VetoDecision, list[str], str]:
    if not facts:
        return VetoDecision.ALLOW, [], ""

    tz = _zone(user_timezone)
    write_when = view.when
    if (
        write_when is None
        and view.kind != KIND_OUTBOUND_DRAFT
        and view.channel == "email"
    ):
        write_when = now or datetime.now(tz)
    if write_when is not None and write_when.tzinfo is None:
        write_when = write_when.replace(tzinfo=tz)
    elif write_when is not None:
        write_when = write_when.astimezone(tz)

    refuse_ids: list[str] = []
    confirm_ids: list[str] = []
    notes: list[str] = []

    for fact in facts:
        decision, note = _match_one(view, fact, write_when, tz)
        cid = str(fact.id)
        if decision is VetoDecision.REFUSE:
            refuse_ids.append(cid)
            notes.append(note)
        elif decision is VetoDecision.CONFIRM:
            confirm_ids.append(cid)
            notes.append(note)

    if refuse_ids:
        error = notes[0] if notes else "This write violates a standing constraint."
        return VetoDecision.REFUSE, refuse_ids, error
    if confirm_ids:
        error = (
            notes[0]
            if notes
            else "This write may violate a standing constraint. Confirm to proceed."
        )
        return VetoDecision.CONFIRM, confirm_ids, error
    return VetoDecision.ALLOW, [], ""


def _match_one(
    view: ConstraintWriteView,
    fact: ReviewedConstraint,
    write_when: datetime | None,
    tz: ZoneInfo,
) -> tuple[VetoDecision, str]:
    text = fact.value.lower()
    channels = _constraint_channels(text)
    compatible = _channel_compatible(view.channel, channels)
    party_hit = _party_hit(view.parties, text)
    window = _parse_time_window(text)
    ignore_time = view.kind == KIND_OUTBOUND_DRAFT
    in_window = False
    if window is not None and not ignore_time and write_when is not None:
        local = write_when.astimezone(tz).time()
        in_window = _time_in_window(local, window)

    if compatible == "no" and not party_hit:
        return VetoDecision.ALLOW, ""
    if compatible == "no" and party_hit:
        return (
            VetoDecision.CONFIRM,
            f"Constraint {fact.value!r} may apply to this write.",
        )

    if party_hit and compatible == "yes":
        if view.kind == KIND_OUTBOUND_DRAFT:
            return (
                VetoDecision.CONFIRM,
                f"Draft may violate standing constraint: {fact.value}",
            )
        return VetoDecision.REFUSE, f"Blocked by standing constraint: {fact.value}"

    if party_hit and compatible == "maybe":
        if view.kind == KIND_OUTBOUND_DRAFT:
            return (
                VetoDecision.CONFIRM,
                f"Draft may violate standing constraint: {fact.value}",
            )
        return VetoDecision.REFUSE, f"Blocked by standing constraint: {fact.value}"

    if window is not None and not ignore_time:
        if write_when is None:
            if compatible in {"yes", "maybe"}:
                return (
                    VetoDecision.CONFIRM,
                    f"Time-window constraint may apply: {fact.value}",
                )
            return VetoDecision.ALLOW, ""
        if in_window and compatible == "yes":
            return VetoDecision.REFUSE, f"Blocked by standing constraint: {fact.value}"
        if in_window and compatible == "maybe":
            return (
                VetoDecision.CONFIRM,
                f"Time-window constraint may apply: {fact.value}",
            )
        return VetoDecision.ALLOW, ""

    if compatible == "yes" and not party_hit and window is None:
        return (
            VetoDecision.CONFIRM,
            f"Constraint may apply: {fact.value}",
        )
    if compatible == "maybe" and not party_hit and window is None:
        return (
            VetoDecision.CONFIRM,
            f"Constraint may apply: {fact.value}",
        )
    return VetoDecision.ALLOW, ""


def _constraint_channels(text: str) -> set[str]:
    tokens = set(_tokenize(text))
    found: set[str] = set()
    if tokens & _EMAIL_TOKENS:
        found.add("email")
    if tokens & _CALENDAR_TOKENS:
        found.add("calendar")
    if tokens & _REMINDER_TOKENS:
        found.add("reminder")
    return found


def _channel_compatible(
    write_channel: str | None, constraint_channels: set[str]
) -> str:
    if not constraint_channels:
        return "maybe"
    if write_channel and write_channel in constraint_channels:
        return "yes"
    if write_channel is None:
        return "maybe"
    return "no"


def _party_hit(parties: list[str], constraint_text: str) -> bool:
    haystack = constraint_text.lower()
    for party in parties:
        token = party.strip().lower()
        if len(token) < 3:
            continue
        local = token.split("@", 1)[0]
        if len(local) >= 3 and local in haystack:
            return True
        if token in haystack:
            return True
    return False


def _tokenize(text: str) -> list[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return [part for part in cleaned.split() if part]


def _parse_time_window(text: str) -> tuple[time, time] | None:
    after = re.search(
        r"after\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
        text,
        re.IGNORECASE,
    )
    before = re.search(
        r"before\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
        text,
        re.IGNORECASE,
    )
    start: time | None = None
    end: time | None = None
    if after:
        start = _to_time(after.group(1), after.group(2), after.group(3))
        end = time(23, 59, 59)
    if before:
        end = _to_time(before.group(1), before.group(2), before.group(3))
        if start is None:
            start = time(0, 0)
    if start is None or end is None:
        return None
    return start, end


def _to_time(hour_s: str, minute_s: str | None, ampm: str | None) -> time:
    hour = int(hour_s)
    minute = int(minute_s) if minute_s else 0
    if ampm:
        marker = ampm.lower()
        if marker == "pm" and hour != 12:
            hour += 12
        if marker == "am" and hour == 12:
            hour = 0
    hour = min(max(hour, 0), 23)
    minute = min(max(minute, 0), 59)
    return time(hour, minute)


def _time_in_window(local: time, window: tuple[time, time]) -> bool:
    start, end = window
    if start <= end:
        return start <= local <= end
    return local >= start or local <= end


def _coerce_when(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


async def load_reviewed_constraints(store: Any) -> list[ReviewedConstraint]:
    pool = getattr(store, "pool", None)
    if pool is None:
        pool = getattr(store, "_pool", None)
    if pool is None:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, value
            FROM memory_facts
            WHERE reviewed = true
              AND contradicted = false
              AND predicate = 'constraint'
            ORDER BY created_at DESC
            LIMIT 50
            """
        )
    return [ReviewedConstraint(id=row["id"], value=row["value"]) for row in rows]


class ConstraintVetoHook(BaseHarnessHook):
    """Refuse or confirm constraint-gated writes before the tool body runs."""

    def __init__(
        self,
        store: Any = None,
        user_timezone: str = "UTC",
        constraints: list[ReviewedConstraint] | None = None,
        now: datetime | None = None,
    ) -> None:
        self._store = store
        self._user_timezone = user_timezone
        self._constraints = constraints
        self._now = now

    async def on_tool_start(self, event: ToolStartEvent) -> dict[str, Any] | None:
        try:
            spec = get_tool(event.tool_name)
        except Exception:
            return None
        if not spec.constraint_gate:
            return None

        view = view_from_describe(event.tool_name, event.args, spec.constraint_describe)
        facts = await self._facts_for(event)
        decision, ids, error = match_constraints(
            view,
            facts,
            user_timezone=self._user_timezone,
            now=self._now,
        )
        if decision is VetoDecision.ALLOW:
            return None

        payload = veto_payload(ids, error)
        if decision is VetoDecision.CONFIRM:
            if await self._user_approved(event, error):
                return None
        raise HookAbort(event.tool_name, error, result=payload)

    async def _facts_for(self, event: ToolStartEvent) -> list[ReviewedConstraint]:
        if self._constraints is not None:
            return self._constraints
        cached = getattr(event.ctx, _CTX_CACHE_ATTR, None)
        if cached is not None:
            return cached
        facts = await load_reviewed_constraints(self._store)
        setattr(event.ctx, _CTX_CACHE_ATTR, facts)
        return facts

    async def _user_approved(self, event: ToolStartEvent, prompt: str) -> bool:
        interrupt_fn = tool_interrupt_fn.get()
        if interrupt_fn is None:
            return False
        decision = interrupt_fn(
            {
                "kind": "constraint",
                "prompt": prompt,
                "editable": False,
                "proposed": "",
                "tool": event.tool_name,
                "args": event.args,
            }
        )
        choice = "approve"
        if isinstance(decision, dict):
            choice = str(decision.get("choice") or "approve")
        elif isinstance(decision, str):
            choice = decision
        return choice == "approve"
