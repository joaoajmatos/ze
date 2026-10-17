"""Pure composition rules: records in, primitives out. No I/O, no clock reads."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, TypeVar

from ze_automation.goals.types import STUCK_IDLE_DAYS, GoalProgress
from ze_automation.holds.types import HeldWrite
from ze_automation.workflow.failure import failure_summary
from ze_automation.workflow.types import Workflow
from ze_components.claims import HEADLINE_MAX
from ze_components import (
    CardAction,
    ClaimCard,
    ClaimPosture,
    Readout,
    TimelineEntry,
    claim_card,
    claim_timeline,
    headline,
    headline_text,
)
from ze_worldstate.types import LoopState, OpenLoop

from ze_priority.compose.types import Draft, SourceSnapshot, WorkflowDigest
from ze_priority.matching import MATCH_FLOOR, cosine
from ze_priority.types import (
    GoalSignal,
    LoopSignal,
    PriorityItem,
    RelationshipSignal,
)

WINDOW_DAYS = 7
LIST_CAP = 6
COMPOSITION_CAP = 12
PERSON_CAP = 2
SUMMARY_MAX = 800

_COULD_NOT_READ = "I could not read any of my sources just now."


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return _aware(value).isoformat() if value is not None else None


def _days_since(moment: datetime, now: datetime) -> int:
    return max(0, int((now - _aware(moment)).total_seconds() // 86400))


def _days_until(moment: datetime, now: datetime) -> int:
    return max(0, math.ceil((_aware(moment) - now).total_seconds() / 86400))


_SOURCE_WORDS = {
    "conversation": "a conversation with you",
    "ingestion": "a document you added",
    "user_declared": "what you told me",
    "email": "your email",
    "calendar": "your calendar",
}


def _source_label(key: str) -> str:
    return _SOURCE_WORDS.get(key, key.replace("_", " "))


def _loop_posture(loop: OpenLoop) -> ClaimPosture:
    assert loop.id is not None
    return ClaimPosture(
        kind=loop.claim_kind.value,
        subject="loop",
        ref_id=str(loop.id),
        confidence=loop.confidence,
        source=loop.provenance,
        as_of=_iso(loop.updated_at or loop.confirmed_at or loop.created_at),
        state=loop.state.value,
        slipped=loop.state == LoopState.DRIFTING,
    )


def _loop_timing(loop: OpenLoop, now: datetime) -> Readout | None:
    if loop.drift_deadline is None:
        return None
    if loop.state == LoopState.DRIFTING:
        days = _days_since(loop.drift_deadline, now)
        value = "slipped today" if days == 0 else f"slipped {days} d ago"
        return Readout("Deadline", value, "hot")
    days = _days_until(loop.drift_deadline, now)
    return Readout("Deadline", "due today" if days == 0 else f"due in {days} d")


def _loop_card(
    loop: OpenLoop,
    now: datetime,
    *,
    lines: list[str] | None = None,
    actions: list[CardAction] | None = None,
) -> ClaimCard:
    posture = _loop_posture(loop)
    readouts = [r for r in (_loop_timing(loop, now),) if r]
    readouts.append(Readout("Confidence", f"{loop.confidence:.2f}"))
    if lines is None:
        lines = (
            [loop.drift_rationale] if posture.slipped and loop.drift_rationale else []
        )
    return claim_card(
        loop.title, posture, lines=lines, readouts=readouts, actions=actions
    )


def _goal_card(
    goal: GoalProgress,
    now: datetime,
    *,
    stuck: bool = False,
    awaiting_gate: bool = False,
    actions: list[CardAction] | None = None,
    span: int = 4,
    lines: list[str] | None = None,
) -> ClaimCard:
    if stuck:
        state = "stuck"
    elif awaiting_gate:
        state = "awaiting_gate"
    else:
        state = goal.goal.status.value
    posture = ClaimPosture(
        kind="priority",
        subject="goal",
        ref_id=str(goal.goal.id),
        source="goal",
        as_of=_iso(
            goal.last_progress_at or goal.gate_open_since or goal.goal.created_at
        ),
        state=state,
        slipped=stuck or goal.stuck_since is not None,
    )
    readouts = [
        Readout("Milestones", f"{goal.milestones_done}/{goal.milestones_total}")
    ]
    if stuck and goal.stuck_since is not None:
        days = _days_since(goal.stuck_since, now)
        waiting = goal.gate_open_since is not None
        text = (
            f"waiting on you for {days} d" if waiting else f"no progress for {days} d"
        )
        readouts.append(Readout("Status", text, "hot"))
    elif awaiting_gate and goal.gate_open_since is not None:
        readouts.append(
            Readout("Gate", f"waiting {_days_since(goal.gate_open_since, now)} d")
        )
    if lines is None:
        lines = [f"Next: {goal.next_milestone}"] if goal.next_milestone else []
    return claim_card(
        goal.goal.title,
        posture,
        span=span,  # type: ignore[arg-type]
        lines=lines,
        readouts=readouts,
        progress_done=goal.milestones_done,
        progress_total=goal.milestones_total,
        actions=actions,
        needs_user=awaiting_gate,
        tone="cream" if awaiting_gate else None,
    )


def _person_card(item: PriorityItem) -> ClaimCard:
    signal = item.signal
    assert isinstance(signal, RelationshipSignal)
    posture = ClaimPosture(
        kind=item.claim_kind.value,
        subject="person",
        ref_id=str(item.source_id),
        source="relationship",
        as_of=_iso(item.activity_at),
        state="stale",
    )
    return claim_card(
        item.title, posture, lines=[f"Last contact {signal.days_ago} d ago"]
    )


def _watching(snapshot: SourceSnapshot) -> int:
    open_states = (LoopState.ACTIVE, LoopState.DRIFTING)
    return sum(1 for loop in snapshot.loops or [] if loop.state in open_states)


def _failed(snapshot: SourceSnapshot) -> list[str]:
    return sorted(snapshot.failed)


def _summary(lines: list[str], snapshot: SourceSnapshot) -> str:
    failed = _failed(snapshot)
    if failed:
        lines = [*lines, "could not read: " + ", ".join(failed)]
    text = "\n".join(lines)
    return text if len(text) <= SUMMARY_MAX else text[: SUMMARY_MAX - 1].rstrip() + "…"


def _unreadable(snapshot: SourceSnapshot, *required: str) -> Draft | None:
    if required and all(key in snapshot.failed for key in required):
        text = headline_text("COULD NOT READ THE WORLD")
        return Draft(text, [headline(text)], _COULD_NOT_READ, _failed(snapshot))
    return None


def _oldest_first(loops: list[OpenLoop]) -> list[OpenLoop]:
    return sorted(
        loops,
        key=lambda loop: (
            loop.drift_deadline is None,
            _aware(loop.drift_deadline).timestamp() if loop.drift_deadline else 0.0,
        ),
    )


def _timing_text(card: ClaimCard) -> str:
    for readout in reversed(card.readouts):
        if readout.label in ("Deadline", "Status", "Gate"):
            return readout.value
    return card.readouts[-1].value if card.readouts else ""


def slipping(snapshot: SourceSnapshot, now: datetime) -> Draft:
    if (down := _unreadable(snapshot, "loops", "goals", "priority")) is not None:
        return down

    loops = snapshot.loops or []
    slipped_loops = _oldest_first(
        [lp for lp in loops if lp.state == LoopState.DRIFTING]
    )
    stuck_goals = sorted(
        (g for g in snapshot.goals or [] if g.stuck_since is not None),
        key=lambda g: _aware(g.stuck_since).timestamp(),  # type: ignore[arg-type]
    )
    window_end = now + timedelta(days=WINDOW_DAYS)
    window_start = now - timedelta(days=WINDOW_DAYS)
    dated_active = [
        lp
        for lp in loops
        if lp.state == LoopState.ACTIVE and lp.drift_deadline is not None
    ]
    at_risk = _oldest_first(
        [lp for lp in dated_active if now <= _aware(lp.drift_deadline) <= window_end]  # type: ignore[arg-type]
    )
    recent_past = _oldest_first(
        [lp for lp in dated_active if window_start <= _aware(lp.drift_deadline) < now]  # type: ignore[arg-type]
    )

    n_slipped = len(slipped_loops) + len(stuck_goals)
    n_at_risk = len(at_risk)
    head = (
        headline("NOTHING SLIPPING")
        if n_slipped == 0 and n_at_risk == 0
        else headline(f"{n_slipped} SLIPPING · {n_at_risk} AT RISK")
    )

    cards: list[ClaimCard] = []
    cards += [_loop_card(lp, now) for lp in slipped_loops[:LIST_CAP]]
    cards += [_goal_card(g, now, stuck=True) for g in stuck_goals[:LIST_CAP]]
    cards += [_loop_card(lp, now) for lp in at_risk[:LIST_CAP]]
    persons = [
        i
        for i in (snapshot.ranking.items if snapshot.ranking else [])
        if i.source_kind == "relationship"
    ][:PERSON_CAP]
    cards += [_person_card(p) for p in persons]
    cards = cards[:COMPOSITION_CAP]

    entries = [
        TimelineEntry(lp.title, _loop_posture(lp), _iso(lp.drift_deadline))
        for lp in [
            *slipped_loops[:LIST_CAP],
            *at_risk[:LIST_CAP],
            *recent_past[:LIST_CAP],
        ]
    ]
    components: list[object] = [head]
    if entries:
        components.append(claim_timeline("Past 7 days to next 7", entries))
    components.extend(cards)

    if n_slipped or n_at_risk:
        lines = [f"{n_slipped} slipping, {n_at_risk} at risk."]
    else:
        lines = ["Nothing is slipping and nothing is due within 7 days."]
    for card in cards:
        if card.claim.subject == "person":
            lines.append(f"stale: {card.title} ({card.lines[0]})")
            continue
        if card.claim.state == "stuck":
            label = "stuck"
        elif card.claim.slipped:
            label = "slipped"
        else:
            label = "at risk"
        lines.append(f"{label}: {card.title} ({_timing_text(card)})")
    lines.append(f"watching: {_watching(snapshot)} open concerns")
    return Draft(head.text, components, _summary(lines, snapshot), _failed(snapshot))


def _held_title(hold: HeldWrite) -> str:
    first = hold.items[0] if hold.items else {}
    phrase = first.get("effect_phrase") or "A step needs approval"
    summary = first.get("summary")
    title = f"{phrase}: {summary}" if summary else phrase
    if len(hold.items) > 1:
        title += f" (+{len(hold.items) - 1} more)"
    return title


def _held_card(hold: HeldWrite, now: datetime) -> ClaimCard:
    posture = ClaimPosture(
        kind=None,
        subject="held_write",
        ref_id=hold.request_id,
        source=hold.source,
        as_of=_iso(hold.created_at),
        state="open",
    )
    owner = hold.payload.get("source_name")
    line = f"From {hold.source} '{owner}'" if owner else f"From {hold.source}"
    readouts = []
    if hold.expires_at is not None:
        hours = max(0, int((_aware(hold.expires_at) - now).total_seconds() // 3600))
        readouts.append(Readout("Expires", f"expires in {hours} h"))
    return claim_card(
        _held_title(hold),
        posture,
        lines=[line],
        readouts=readouts,
        actions=[
            CardAction("Approve", "approve_held_write", hold.request_id),
            CardAction("Deny", "deny_held_write", hold.request_id),
        ],
        needs_user=True,
    )


def _gate_card(goal: GoalProgress, now: datetime) -> ClaimCard:
    assert goal.gate_id is not None
    return _goal_card(
        goal,
        now,
        awaiting_gate=True,
        span=8,
        lines=[goal.gate_title] if goal.gate_title else [],
        actions=[
            CardAction("Approve", "approve_gate", str(goal.gate_id)),
            CardAction("Open", "open", str(goal.goal.id)),
        ],
    )


def decisions(snapshot: SourceSnapshot, now: datetime) -> Draft:
    if (down := _unreadable(snapshot, "loops", "goals", "held_writes")) is not None:
        return down

    holds = sorted(
        (
            h
            for h in snapshot.held_writes or []
            if h.expires_at is None or _aware(h.expires_at) > now
        ),
        key=lambda h: (
            h.expires_at is None,
            _aware(h.expires_at).timestamp() if h.expires_at else 0.0,
        ),
    )
    gates = sorted(
        (g for g in snapshot.goals or [] if g.gate_id is not None),
        key=lambda g: (
            g.gate_open_since is None,
            _aware(g.gate_open_since).timestamp() if g.gate_open_since else 0.0,
        ),
    )
    suspicions = sorted(
        (lp for lp in snapshot.loops or [] if lp.state == LoopState.SUSPECTED),
        key=lambda lp: -lp.confidence,
    )

    total = len(holds) + len(gates) + len(suspicions)
    head = headline(f"{total} TO DECIDE" if total else "NOTHING TO DECIDE")

    cards: list[ClaimCard] = []
    cards += [_held_card(h, now) for h in holds[:LIST_CAP]]
    cards += [_gate_card(g, now) for g in gates[:LIST_CAP]]
    cards += [
        _loop_card(
            lp,
            now,
            lines=[f"Seen in {_source_label(lp.provenance)}"],
            actions=[
                CardAction("Yes, track it", "confirm_loop", str(lp.id)),
                CardAction("Drop", "drop_loop", str(lp.id)),
            ],
        )
        for lp in suspicions[:LIST_CAP]
    ]

    if total:
        lines = [
            f"{total} to decide: {len(holds)} held write(s), "
            f"{len(gates)} goal gate(s), {len(suspicions)} suspected loop(s)."
        ]
    else:
        lines = ["Nothing is waiting on a decision."]
    lines += [f"{c.claim.subject}: {c.title}" for c in cards]
    return Draft(
        head.text, [head, *cards], _summary(lines, snapshot), _failed(snapshot)
    )


_T = TypeVar("_T")
_NO_EMBEDDER = "I can't match topics right now."


def _ago(moment: datetime, now: datetime) -> str:
    hours = max(0, int((now - _aware(moment)).total_seconds() // 3600))
    return f"{hours} h ago" if hours < 48 else f"{hours // 24} d ago"


def _in(moment: datetime, now: datetime) -> str:
    hours = max(0, int((_aware(moment) - now).total_seconds() // 3600))
    return f"in {hours} h" if hours < 48 else f"in {hours // 24} d"


def _encode(embedder: Any, texts: list[str]) -> list[Any]:
    """One batched embedder call for all texts."""
    return list(embedder.encode_passage(texts)) if texts else []


def _matches(
    items: list[_T],
    topic_vec: Any,
    embedder: Any,
    texts: Callable[[_T], list[str]],
) -> list[_T]:
    per_item = [[t for t in texts(item) if t] for item in items]
    vectors = iter(_encode(embedder, [t for group in per_item for t in group]))
    scored = []
    for item, group in zip(items, per_item):
        score = max((cosine(topic_vec, next(vectors)) for _ in group), default=0.0)
        if score >= MATCH_FLOOR:
            scored.append((score, item))
    scored.sort(key=lambda pair: -pair[0])
    return [item for _, item in scored[:LIST_CAP]]


def match_workflows(
    workflows: list[Workflow], topic: str, embedder: Any
) -> list[Workflow]:
    """The workflows a topic names, best match first. Empty without an embedder."""
    if embedder is None:
        return []
    return _matches(
        workflows,
        _encode(embedder, [topic])[0],
        embedder,
        lambda w: [f"{w.name} {w.description}".strip()],
    )


def _workflow_card(digest: WorkflowDigest, now: datetime) -> ClaimCard:
    workflow, execution = digest.workflow, digest.last_execution
    lines: list[str] = []
    state: str | None
    if not workflow.enabled:
        state = "off"
    elif execution is None:
        state = "never_run"
    elif execution.status == "failed":
        state = "failed"
        summary = failure_summary(execution)
        lines = [summary] if summary else []
    elif execution.status == "completed":
        state = "ok"
    else:
        state = None
    posture = ClaimPosture(
        kind=None,
        subject="workflow",
        ref_id=str(workflow.id),
        source="workflow",
        as_of=_iso(workflow.last_run_at),
        state=state,
        slipped=state == "failed",
    )
    readouts = []
    if workflow.last_run_at is not None:
        readouts.append(Readout("Last run", _ago(workflow.last_run_at, now)))
    if workflow.enabled and workflow.next_run_at is not None:
        readouts.append(Readout("Next run", _in(workflow.next_run_at, now)))
    return claim_card(workflow.name, posture, lines=lines, readouts=readouts)


def _hypothesis_card(item: PriorityItem) -> ClaimCard:
    signal = item.signal
    posture = ClaimPosture(
        kind=item.claim_kind.value,
        subject="hypothesis",
        ref_id=str(item.source_id),
        confidence=getattr(signal, "confidence", None),
        source="correlation",
        as_of=_iso(item.activity_at),
        state="open",
    )
    return claim_card(item.title, posture)


def _topic_headline(topic: str, slipped: int, workflows: int) -> str:
    suffix = f" · {slipped} SLIPPED · {workflows} WORKFLOWS"
    room = HEADLINE_MAX - len(suffix)
    return f"{headline_text(topic)[: max(room, 0)].rstrip()}{suffix}"


def topic(snapshot: SourceSnapshot, topic: str, embedder: Any, now: datetime) -> Draft:
    """Cards for what the stores hold about `topic`. `snapshot.workflows` holds the
    workflows already matched by `match_workflows`, with their last execution."""
    if (
        down := _unreadable(snapshot, "loops", "goals", "workflows", "priority")
    ) is not None:
        return down
    empty = headline(f"NOTHING ON {topic}")
    if embedder is None:
        return Draft(empty.text, [empty], _NO_EMBEDDER, _failed(snapshot))

    vec = _encode(embedder, [topic])[0]
    loops = _matches(snapshot.loops or [], vec, embedder, lambda lp: [lp.title])
    goals = _matches(
        snapshot.goals or [],
        vec,
        embedder,
        lambda g: [g.goal.title, g.goal.objective],
    )
    hypotheses = _matches(
        [
            i
            for i in (snapshot.ranking.items if snapshot.ranking else [])
            if i.source_kind == "hypothesis"
        ],
        vec,
        embedder,
        lambda i: [i.match_text or i.title, i.title],
    )
    workflows = (snapshot.workflows or [])[:LIST_CAP]

    cards: list[ClaimCard] = []
    cards += [_loop_card(lp, now) for lp in loops]
    cards += [_goal_card(g, now, stuck=g.stuck_since is not None) for g in goals]
    cards += [_workflow_card(w, now) for w in workflows]
    cards += [_hypothesis_card(i) for i in hypotheses]

    if not cards:
        lines = [f"Ze holds nothing open about {topic}."]
        return Draft(empty.text, [empty], _summary(lines, snapshot), _failed(snapshot))

    slipped = sum(1 for c in cards if c.claim.slipped)
    head = headline(_topic_headline(topic, slipped, len(workflows)))
    lines = [f"{len(cards)} item(s) about {topic}, {slipped} slipped."]
    for card in cards:
        state = card.claim.state or "unknown"
        line = f"{card.claim.subject}: {card.title} ({state})"
        if (
            card.claim.subject == "workflow"
            and card.claim.state == "failed"
            and card.lines
        ):
            line += f" - {card.lines[0]}"
        lines.append(line)
    return Draft(
        head.text, [head, *cards], _summary(lines, snapshot), _failed(snapshot)
    )


def _loop_card_from_item(item: PriorityItem, now: datetime) -> ClaimCard:
    signal = item.signal
    assert isinstance(signal, LoopSignal)
    drifting = signal.state == LoopState.DRIFTING
    posture = ClaimPosture(
        kind=item.claim_kind.value,
        subject="loop",
        ref_id=str(item.source_id),
        confidence=signal.confidence,
        as_of=_iso(item.activity_at),
        state=signal.state.value,
        slipped=drifting,
    )
    lines = [signal.drift_rationale] if drifting and signal.drift_rationale else []
    return claim_card(item.title, posture, lines=lines)


def _goal_card_from_item(item: PriorityItem) -> ClaimCard:
    signal = item.signal
    assert isinstance(signal, GoalSignal)
    stuck = signal.idle_days >= STUCK_IDLE_DAYS
    if stuck:
        state = "stuck"
    else:
        state = "awaiting_gate" if signal.kind == "awaiting_gate" else "active"
    posture = ClaimPosture(
        kind=item.claim_kind.value,
        subject="goal",
        ref_id=str(item.source_id),
        source="goal",
        as_of=_iso(item.activity_at),
        state=state,
        slipped=stuck,
    )
    readouts = (
        [Readout("Status", f"no progress for {signal.idle_days} d", "hot")]
        if stuck
        else []
    )
    return claim_card(item.title, posture, readouts=readouts)


def mention_card(
    item: PriorityItem | None, now: datetime, *, loop: OpenLoop | None = None
) -> ClaimCard | None:
    """A card for one inline mention. A loop record, when given, is the posture's source;
    otherwise the ranked item's signal is. Returns None when there is nothing to read."""
    if loop is not None:
        return _loop_card(loop, now, lines=None)
    if item is None:
        return None
    if item.source_kind == "loop" and isinstance(item.signal, LoopSignal):
        return _loop_card_from_item(item, now)
    if item.source_kind == "goal" and isinstance(item.signal, GoalSignal):
        return _goal_card_from_item(item)
    if item.source_kind == "hypothesis":
        return _hypothesis_card(item)
    if item.source_kind == "relationship" and isinstance(
        item.signal, RelationshipSignal
    ):
        return _person_card(item)
    return None
