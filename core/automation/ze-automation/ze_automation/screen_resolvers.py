"""Screen resolvers for goals, workflows and held writes (phase 195)."""

from __future__ import annotations

from typing import Any

from ze_agents.claims import ClaimKind
from ze_agents.screen import (
    ResolveContext,
    ScreenLine,
    ScreenPosture,
    ScreenRef,
    ScreenResolver,
    ScreenStatus,
    as_utc,
    parse_uuid,
    resolve_each,
    sanitize_text,
    time_ago,
)
from ze_automation.goals.types import GateStatus, MilestoneStatus
from ze_automation.workflow.failure import failure_summary

_OPEN_GATES = (GateStatus.PENDING, GateStatus.AWAITING_APPROVAL)


def _words(value: Any) -> str:
    return str(getattr(value, "value", value)).replace("_", " ")


class GoalScreenResolver:
    kinds = frozenset({"goal", "goal_gate"})

    def __init__(self, goal_store: Any) -> None:
        self._goals = goal_store

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        return await resolve_each(refs, lambda ref: self._load(ref, ctx))

    async def _load(self, ref: ScreenRef, ctx: ResolveContext) -> ScreenLine | None:
        goal_id = parse_uuid(ref.id)
        if goal_id is None:
            return None
        if ref.kind == "goal_gate":
            return await self._gate(ref, goal_id, ctx)
        detail = await self._goals.get_goal_detail(goal_id)
        if detail is None:
            return None
        goal = detail.goal
        done = sum(
            1 for m in detail.milestones if m.status is MilestoneStatus.COMPLETED
        )
        pending = sorted(
            (
                m
                for m in detail.milestones
                if m.status not in (MilestoneStatus.COMPLETED, MilestoneStatus.SKIPPED)
            ),
            key=lambda m: m.sequence,
        )
        parts = [_words(goal.status), f"{done}/{len(detail.milestones)} milestones"]
        if pending:
            parts.append(f'next: "{sanitize_text(pending[0].title, 60)}"')
        gate = next(
            (g for g in detail.gates if g.status in _OPEN_GATES and g.fired_at), None
        )
        if gate is not None:
            since = time_ago(as_utc(gate.fired_at), ctx.now)
            parts.append(
                f'waiting on gate "{sanitize_text(gate.title, 60)}" since {since}'
            )
        return ScreenLine(
            ref=ref,
            label=goal.title,
            summary=", ".join(parts[:2]) + "".join(f"; {p}" for p in parts[2:]),
            posture=ScreenPosture(
                kind=ClaimKind.PRIORITY,
                source="goal",
                updated_at=as_utc(goal.updated_at),
            ),
        )

    async def _gate(
        self, ref: ScreenRef, gate_id, ctx: ResolveContext
    ) -> ScreenLine | None:
        gate = await self._goals.get_gate(gate_id)
        if gate is None:
            return None
        parts = [_words(gate.status)]
        if gate.fired_at:
            parts.append(f"fired {time_ago(as_utc(gate.fired_at), ctx.now)}")
        try:
            detail = await self._goals.get_goal_detail(gate.goal_id)
        except Exception:
            detail = None
        if detail is not None:
            parts.append(f'goal "{sanitize_text(detail.goal.title, 60)}"')
        return ScreenLine(
            ref=ref,
            label=gate.title,
            summary=", ".join(parts),
            posture=ScreenPosture(
                kind=ClaimKind.PRIORITY,
                source="goal",
                updated_at=as_utc(gate.resolved_at or gate.fired_at or gate.created_at),
            ),
        )


class WorkflowScreenResolver:
    kinds = frozenset({"workflow", "workflow_execution"})

    def __init__(self, workflow_store: Any) -> None:
        self._workflows = workflow_store

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        return await resolve_each(refs, lambda ref: self._load(ref, ctx))

    async def _load(self, ref: ScreenRef, ctx: ResolveContext) -> ScreenLine | None:
        if ref.kind == "workflow_execution":
            return await self._execution(ref, ctx)
        workflow_id = parse_uuid(ref.id)
        if workflow_id is None:
            return None
        wf = await self._workflows.get(workflow_id)
        if wf is None:
            return None
        parts = ["enabled" if wf.enabled else "disabled"]
        parts.append(
            f'schedule "{sanitize_text(wf.schedule, 60)}"'
            if wf.schedule
            else "run on request"
        )
        runs = await self._workflows.list_executions(wf.id, 1)
        if runs:
            last = runs[0]
            if last.status == "failed":
                reason = failure_summary(last)
                parts.append(
                    f"last run failed: {sanitize_text(reason, 120)}"
                    if reason
                    else "last run failed"
                )
            else:
                parts.append(f"last run {_words(last.status)}")
        if wf.next_run_at and wf.enabled:
            parts.append(f"next run {wf.next_run_at.strftime('%Y-%m-%d %H:%M')}")
        return ScreenLine(
            ref=ref,
            label=wf.name,
            summary="; ".join(parts),
            posture=ScreenPosture(source="workflow", updated_at=as_utc(wf.updated_at)),
        )

    async def _execution(
        self, ref: ScreenRef, ctx: ResolveContext
    ) -> ScreenLine | None:
        label = sanitize_text(ref.label or "Workflow run", 120)
        workflow_id = parse_uuid(ref.parent_id)
        execution_id = parse_uuid(ref.id)
        if workflow_id is None:
            # Never a false "no longer exists": the record was not looked up at all.
            return ScreenLine(
                ref=ref,
                label=label,
                summary="missing parent",
                status=ScreenStatus.FAILED,
            )
        if execution_id is None:
            return None
        ex = await self._workflows.get_execution(workflow_id, execution_id)
        if ex is None:
            return None
        total = len(ex.steps_snapshot)
        ran = len(ex.step_results)
        steps = f"{ran} of {total} steps" if total else f"{ran} steps"
        parts = [_words(ex.status), steps]
        if ex.started_at and ex.completed_at:
            parts.append(
                f"{int((as_utc(ex.completed_at) - as_utc(ex.started_at)).total_seconds())} s"
            )
        if ex.status == "failed":
            reason = failure_summary(ex)
            if reason:
                parts.append(sanitize_text(reason, 120))
        title = (
            label
            if ref.label
            else (
                f"Run of {ex.started_at.strftime('%b %d')}"
                if ex.started_at
                else "Workflow run"
            )
        )
        return ScreenLine(
            ref=ref,
            label=title,
            summary=", ".join(parts[:3]) + "".join(f"; {p}" for p in parts[3:]),
            posture=ScreenPosture(
                source="workflow",
                updated_at=as_utc(ex.completed_at or ex.started_at or ex.created_at),
            ),
        )


class HeldWriteScreenResolver:
    kinds = frozenset({"held_write"})

    def __init__(self, held_store: Any) -> None:
        self._holds = held_store

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        return await resolve_each(refs, lambda ref: self._load(ref, ctx))

    async def _load(self, ref: ScreenRef, ctx: ResolveContext) -> ScreenLine | None:
        hold = await self._holds.get(ref.id)
        if hold is None:
            return None
        first = hold.items[0] if hold.items else {}
        what = sanitize_text(
            f"{first.get('effect_phrase') or 'a write'}: {first.get('summary') or ''}".rstrip(
                ": "
            ),
            120,
        )
        parts = [
            what,
            f"{len(hold.items)} item{'s' if len(hold.items) != 1 else ''}",
            _words(hold.status),
        ]
        parts.append(f"from {sanitize_text(hold.source, 30)} run")
        if hold.expires_at and _words(hold.status) == "open":
            left = as_utc(hold.expires_at) - ctx.now
            parts.append(f"expires in {max(0, int(left.total_seconds() // 3600))} h")
        return ScreenLine(
            ref=ref,
            label=sanitize_text(first.get("summary") or "Held write", 120),
            summary="; ".join(parts),
            posture=ScreenPosture(
                source="held_write",
                updated_at=as_utc(hold.decided_at or hold.created_at),
            ),
        )


def build_screen_resolvers(
    *, goal_store: Any, workflow_store: Any, held_write_store: Any | None = None
) -> list[ScreenResolver]:
    resolvers: list[ScreenResolver] = [
        GoalScreenResolver(goal_store),
        WorkflowScreenResolver(workflow_store),
    ]
    if held_write_store is not None:
        resolvers.append(HeldWriteScreenResolver(held_write_store))
    return resolvers
