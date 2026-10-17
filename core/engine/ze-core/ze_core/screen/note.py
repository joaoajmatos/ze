"""Builds the screen note: what the user can see, read by Ze from its own records.

Pure helpers format; `build_screen_note` plans the budget before loading anything, runs one
resolver call per kind in parallel under per-call and total timeouts, and never raises.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime

from ze_agents.claims import ClaimKind
from ze_agents.screen import (
    MAX_SUMMARY,
    ResolveContext,
    ScreenContext,
    ScreenLine,
    ScreenOrigin,
    ScreenPosture,
    ScreenRef,
    ScreenStatus,
    as_utc,
    sanitize_text,
    time_ago,
)
from ze_core.screen.registry import ScreenResolverRegistry
from ze_logging import get_logger

log = get_logger(__name__)

SCREEN_NOTE_CAP = 1200
RESOLVER_TIMEOUT_S = 0.3
TOTAL_TIMEOUT_S = 0.8
SUBJECT_ESTIMATE = 240
OTHER_ESTIMATE = 120

PLACED_KIND = "workspace_placed"
PLACED_ID = "placed"
SLOT_PLACED = -1
SLOT_SUBJECT, SLOT_SELECTION, SLOT_FOCUSED, SLOT_VISIBLE, SLOT_CANVAS = range(5)
_PREFIX = {
    SLOT_PLACED: "Workspace",
    SLOT_SUBJECT: "Subject",
    SLOT_SELECTION: "Selected",
    SLOT_VISIBLE: "Visible",
    SLOT_CANVAS: "On the canvas",
}

HONESTY = (
    "Use this silently. Do not describe the screen back to the user or claim to see "
    "anything not listed here."
)
CHAT_ABOUT = (
    'The user started this chat from that item\'s "Chat about this" action: name it in '
    "your first sentence, then answer; do not recite the rest of the screen."
)
NOTHING_SINGLED_OUT = (
    'Nothing on screen is singled out; if the user says "this" (or the equivalent in '
    "their language), ask which item they mean."
)

_KIND_LABELS = {
    "goal": "Goal",
    "goal_gate": "Goal gate",
    "workflow": "Workflow",
    "workflow_execution": "Workflow run",
    "held_write": "Held write",
    "loop": "Open loop",
    "entity": "Entity",
    "fact": "Fact",
    "procedure": "Procedure",
    "skill": "Skill",
    "workspace_run": "Workspace run",
    "workspace_placed": "Workspace files",
    "notification": "Notification",
    "hypothesis": "Hypothesis",
    "contact": "Contact",
    "reminder": "Reminder",
    "news_article": "News article",
}
_PLACE_LABELS = {
    "world": "World",
    "ask": "Ask",
    "doing": "Doing",
    "mind": "Mind",
    "governance": "Governance",
    "plugin": "A plugin page",
}


@dataclass(frozen=True)
class ResolverRow:
    kind: str
    id: str
    status: ScreenStatus
    ms: int = 0


@dataclass
class ScreenResolution:
    note: str | None = None
    subject_line: str | None = None
    rows: list[ResolverRow] = field(default_factory=list)

    @property
    def note_chars(self) -> int:
        return len(self.note or "")


@dataclass
class _Slot:
    ref: ScreenRef
    slot: int


def kind_label(kind: str) -> str:
    return (
        _KIND_LABELS.get(kind) or sanitize_text(kind, 40).replace("_", " ").capitalize()
    )


def _clip(text: str, cap: int) -> str:
    return text if len(text) <= cap else text[: cap - 1].rstrip() + "…"


def posture_words(posture: ScreenPosture | None) -> list[str]:
    """Claim vocabulary from phase 184; code reads it from the record, never from the client."""
    if posture is None or posture.kind is None:
        return []
    words: list[str] = []
    if posture.kind is ClaimKind.SUSPICION:
        words.append("suspected (not confirmed)")
    elif posture.kind is ClaimKind.INFERENCE:
        words.append("inferred")
    if (
        posture.kind
        in (
            ClaimKind.FACT,
            ClaimKind.IDENTITY,
            ClaimKind.SUSPICION,
            ClaimKind.INFERENCE,
        )
        and posture.confidence is not None
        and posture.confidence < 0.9
    ):
        words.append(f"confidence {posture.confidence:.2f}")
    return words


def format_line(slot: int, line: ScreenLine, now: datetime, estimate: int) -> str:
    kind = kind_label(line.ref.kind)
    label = sanitize_text(line.label or line.ref.label or line.ref.id, 120)
    prefix = _PREFIX.get(slot, "Visible")
    if line.status in (ScreenStatus.FAILED, ScreenStatus.TIMEOUT):
        return _clip(f"{prefix}: Could not load {kind.lower()}.", estimate)
    head = f'{prefix}: {kind} · "{label}"'
    if line.status is ScreenStatus.MISSING:
        return _clip(f"{head} (no longer exists)", estimate)
    parts = [sanitize_text(line.summary, MAX_SUMMARY)] if line.summary else []
    parts.extend(posture_words(line.posture))
    body = "; ".join(p for p in parts if p)
    text = f"{head} — {body}." if body else f"{head}."
    if line.posture and line.posture.updated_at:
        text += f" Updated {time_ago(line.posture.updated_at, now)}."
    if line.status is ScreenStatus.CHANGED:
        text += " (changed since it was shown to you)"
    return _clip(text, estimate)


def _dedupe(ctx: ScreenContext) -> list[_Slot]:
    """One entry per (kind, id), in the highest-priority slot, with missing fields filled from lower ones."""
    ordered: list[_Slot] = []
    if ctx.workspace_placed:
        ordered.append(_Slot(ScreenRef(kind=PLACED_KIND, id=PLACED_ID), SLOT_PLACED))
    for slot, refs in (
        (SLOT_SUBJECT, ctx.subject),
        (SLOT_SELECTION, ctx.selection),
        (SLOT_VISIBLE, ctx.visible),
        (SLOT_CANVAS, tuple(c.ref for c in ctx.canvas if c.ref is not None)),
    ):
        ordered.extend(_Slot(r, slot) for r in refs)
    seen: dict[tuple[str, str], _Slot] = {}
    for item in ordered:
        key = (item.ref.kind, item.ref.id)
        kept = seen.get(key)
        if kept is None:
            seen[key] = item
            continue
        r = kept.ref
        merged = ScreenRef(
            kind=r.kind,
            id=r.id,
            label=r.label or item.ref.label,
            component=r.component or item.ref.component,
            parent_id=r.parent_id or item.ref.parent_id,
            as_of=r.as_of or item.ref.as_of,
        )
        seen[key] = _Slot(merged, kept.slot)
    return list(seen.values())


def _fixed_reserve(ctx: ScreenContext, items: list[_Slot], *, may_cut: bool) -> int:
    """Upper bound of the lines that are not refs, sized from what the context actually has."""
    reserve = len(_header(ctx)) + len(HONESTY) + 2
    if ctx.origin is ScreenOrigin.CHAT_ABOUT:
        reserve += len(CHAT_ABOUT) + 1
    if ctx.focused_module:
        reserve += len(_focused_line(ctx)) + 1
    selected = sum(1 for i in items if i.slot == SLOT_SELECTION)
    if any(i.slot == SLOT_SUBJECT for i in items) or selected == 1:
        reserve += len(_BINDING_THIS) + len(_BINDING_THIS_TAIL) + 40 + 120 + 1
    else:
        reserve += len(NOTHING_SINGLED_OUT) + 1
    if selected:
        reserve += 100
    if may_cut:
        reserve += len(f"+{len(items)} more on screen not included.") + 1
    return reserve


def _plan(ctx: ScreenContext, items: list[_Slot]) -> tuple[list[_Slot], list[_Slot]]:
    """Admit refs in priority order while their estimated line fits; the first subject is never cut."""
    ordered = sorted(items, key=lambda i: i.slot)
    for may_cut in (False, True):
        budget = SCREEN_NOTE_CAP - _fixed_reserve(ctx, items, may_cut=may_cut)
        admitted: list[_Slot] = []
        first_subject = True
        for item in ordered:
            estimate = (
                SUBJECT_ESTIMATE
                if item.slot in (SLOT_SUBJECT, SLOT_PLACED)
                else OTHER_ESTIMATE
            )
            protected = item.slot == SLOT_SUBJECT and first_subject
            if item.slot == SLOT_SUBJECT:
                first_subject = False
            if estimate > budget and not protected:
                break
            budget -= estimate
            admitted.append(item)
        if len(admitted) == len(ordered):
            return admitted, []
    return admitted, ordered[len(admitted) :]


async def _call(resolver, refs: list[ScreenRef], rctx: ResolveContext, timeout: float):
    started = time.monotonic()
    try:
        lines = await asyncio.wait_for(resolver.resolve(refs, rctx), timeout)
        return lines, None, int((time.monotonic() - started) * 1000)
    except asyncio.TimeoutError:
        return None, ScreenStatus.TIMEOUT, int((time.monotonic() - started) * 1000)
    except Exception as exc:  # a resolver never fails a turn
        log.warning("screen_resolver_failed", error=type(exc).__name__)
        return None, ScreenStatus.FAILED, int((time.monotonic() - started) * 1000)


async def _load(
    refs: list[ScreenRef],
    registry: ScreenResolverRegistry,
    rctx: ResolveContext,
    per_call: float,
    deadline: float,
) -> dict[tuple[str, str], tuple[ScreenLine | None, ScreenStatus | None, int]]:
    by_kind: dict[str, list[ScreenRef]] = {}
    for ref in refs:
        by_kind.setdefault(ref.kind, []).append(ref)
    started = time.monotonic()
    out: dict[tuple[str, str], tuple[ScreenLine | None, ScreenStatus | None, int]] = {}
    tasks: dict[asyncio.Task, str] = {}
    for kind, group in by_kind.items():
        resolver = registry.resolver_for(kind)
        if resolver is None:
            for r in group:
                out[(r.kind, r.id)] = (None, ScreenStatus.FAILED, 0)
            continue
        tasks[asyncio.ensure_future(_call(resolver, group, rctx, per_call))] = kind
    if tasks:
        remaining = max(0.0, deadline - time.monotonic())
        done, pending = await asyncio.wait(tasks, timeout=remaining)
        for task in pending:
            task.cancel()
        for task, kind in tasks.items():
            group = by_kind[kind]
            if task in pending:
                for r in group:
                    out[(r.kind, r.id)] = (
                        None,
                        ScreenStatus.TIMEOUT,
                        int((time.monotonic() - started) * 1000),
                    )
                continue
            lines, status, ms = task.result()
            returned = {(ln.ref.kind, ln.ref.id): ln for ln in (lines or [])}
            for r in group:
                line = returned.get((r.kind, r.id))
                out[(r.kind, r.id)] = (line, status if line is None else None, ms)
                if line is None and status is None:
                    out[(r.kind, r.id)] = (None, ScreenStatus.FAILED, ms)
    return out


def _settle(
    line: ScreenLine | None, status: ScreenStatus | None, ref: ScreenRef
) -> ScreenLine:
    if line is None:
        return ScreenLine(
            ref=ref, label=ref.label or ref.id, status=status or ScreenStatus.FAILED
        )
    if (
        line.status is ScreenStatus.OK
        and ref.as_of is not None
        and line.posture is not None
        and line.posture.updated_at is not None
        and as_utc(line.posture.updated_at) > as_utc(ref.as_of)
    ):
        return ScreenLine(
            ref=line.ref,
            label=line.label,
            summary=line.summary,
            posture=line.posture,
            status=ScreenStatus.CHANGED,
            target=line.target,
        )
    return line


_BINDING_THIS = '"this" / "it" / "that" (or the equivalent in the user\'s language) = '
_BINDING_THIS_TAIL = " unless the user names something else."


def _focused_line(ctx: ScreenContext) -> str:
    return f'Focused module: "{sanitize_text(ctx.focused_module, 80)}"'


def _binding(
    subject: ScreenLine | None, selected: list[ScreenLine], cut_selected: int
) -> list[str]:
    lines: list[str] = []
    this = subject or (selected[0] if len(selected) == 1 and subject is None else None)
    if this is not None:
        label = sanitize_text(this.label or this.ref.label or this.ref.id, 120)
        lines.append(
            f'{_BINDING_THIS}{kind_label(this.ref.kind)} "{label}"{_BINDING_THIS_TAIL}'
        )
    else:
        lines.append(NOTHING_SINGLED_OUT)
    if selected:
        n = len(selected)
        noun = "item" if n == 1 else "items"
        more = f" ({cut_selected} more not shown)" if cut_selected else ""
        lines.append(f'"these" / "those" = the {n} selected {noun} shown above{more}.')
    return lines


def _header(ctx: ScreenContext) -> str:
    place = _PLACE_LABELS.get(ctx.place or "")
    where = place or (sanitize_text(ctx.route, 80) if ctx.route else "the app")
    return f"[Screen: {where}. What the user can see right now, read by Ze from its own records:]"


def _render(
    ctx: ScreenContext,
    now: datetime,
    entries: list[tuple[_Slot, ScreenLine]],
    cut: list[_Slot],
) -> tuple[str, ScreenLine | None]:
    """The note for the entries that survive; the binding lines describe only those."""
    subject: ScreenLine | None = None
    selected: list[ScreenLine] = []
    body: list[str] = []
    for item, line in entries:
        estimate = (
            SUBJECT_ESTIMATE
            if item.slot in (SLOT_SUBJECT, SLOT_PLACED)
            else OTHER_ESTIMATE
        )
        body.append(format_line(item.slot, line, now, estimate))
        if item.slot == SLOT_SUBJECT and subject is None:
            subject = line
        if item.slot == SLOT_SELECTION:
            selected.append(line)
    lines = [_header(ctx)]
    if ctx.focused_module:
        lines.append(_focused_line(ctx))
    lines.extend(body)
    if cut:
        lines.append(f"+{len(cut)} more on screen not included.")
    lines.extend(
        _binding(subject, selected, sum(1 for c in cut if c.slot == SLOT_SELECTION))
    )
    if ctx.origin is ScreenOrigin.CHAT_ABOUT and subject is not None:
        lines.append(CHAT_ABOUT)
    lines.append(HONESTY)
    return "\n".join(lines), subject


async def build_screen_note(
    ctx: ScreenContext,
    registry: ScreenResolverRegistry,
    now: datetime,
    *,
    per_call_timeout: float = RESOLVER_TIMEOUT_S,
    total_timeout: float = TOTAL_TIMEOUT_S,
) -> ScreenResolution:
    items = _dedupe(ctx)
    if not items and not ctx.place and not ctx.route and not ctx.focused_module:
        return ScreenResolution()
    admitted, cut = _plan(ctx, items)
    rctx = ResolveContext(
        now=now,
        captured_at=ctx.captured_at,
        origin=ctx.origin,
        placed=ctx.workspace_placed,
    )
    started = time.monotonic()
    deadline = started + total_timeout
    loaded = await _load(
        [i.ref for i in admitted], registry, rctx, per_call_timeout, deadline
    )

    entries: list[tuple[_Slot, ScreenLine]] = []
    rows: list[ResolverRow] = []
    for item in admitted:
        line, status, ms = loaded[(item.ref.kind, item.ref.id)]
        final = _settle(line, status, item.ref)
        entries.append((item, final))
        rows.append(ResolverRow(item.ref.kind, item.ref.id, final.status, ms))
    rows.extend(ResolverRow(i.ref.kind, i.ref.id, ScreenStatus.CUT, 0) for i in cut)

    # One hop, inside the same total deadline: a notification's target.
    shown = {(i.ref.kind, i.ref.id) for i, _ in entries}
    hops = [
        (item, ln.target)
        for item, ln in entries
        if ln.target is not None
        and ln.status is ScreenStatus.OK
        and (ln.target.kind, ln.target.id) not in shown
    ]
    extra: list[tuple[_Slot, ScreenLine]] = []
    if hops and deadline - time.monotonic() > 0:
        hopped = await _load(
            [t for _, t in hops], registry, rctx, per_call_timeout, deadline
        )
        for item, target in hops:
            tline, tstatus, ms = hopped[(target.kind, target.id)]
            final = _settle(tline, tstatus, target)
            extra.append((_Slot(target, item.slot), final))
            rows.append(ResolverRow(target.kind, target.id, final.status, ms))
    elif hops:
        for _, target in hops:
            rows.append(ResolverRow(target.kind, target.id, ScreenStatus.CUT, 0))

    cut_now = list(cut)
    note, subject_line = _render(ctx, now, entries, cut_now)
    for item, line in extra:
        candidate = [*entries, (item, line)]
        trial, _ = _render(ctx, now, candidate, cut_now)
        if len(trial) <= SCREEN_NOTE_CAP:
            entries, note = candidate, trial
        else:
            rows = [
                ResolverRow(r.kind, r.id, ScreenStatus.CUT, 0)
                if (r.kind, r.id) == (line.ref.kind, line.ref.id)
                else r
                for r in rows
            ]
    # Over the cap (a long fixed line): drop the lowest-priority loaded lines, never the first subject.
    while len(note) > SCREEN_NOTE_CAP and len(entries) > 1:
        index = len(entries) - 1
        if entries[index][0].slot == SLOT_SUBJECT and index == 0:
            break
        dropped_item, dropped_line = entries.pop()
        cut_now.append(dropped_item)
        rows = [
            ResolverRow(r.kind, r.id, ScreenStatus.CUT, r.ms)
            if (r.kind, r.id) == (dropped_line.ref.kind, dropped_line.ref.id)
            else r
            for r in rows
        ]
        note, subject_line = _render(ctx, now, entries, cut_now)
    subject_text = None
    if subject_line is not None:
        label = sanitize_text(
            subject_line.label or subject_line.ref.label or subject_line.ref.id, 80
        )
        kind = sanitize_text(subject_line.ref.kind, 30).replace("_", " ")
        subject_text = _clip(f'Screen subject: {kind} "{label}"', 120)
    return ScreenResolution(note=note, subject_line=subject_text, rows=rows)
