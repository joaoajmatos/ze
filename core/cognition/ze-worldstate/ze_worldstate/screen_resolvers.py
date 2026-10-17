"""Screen resolver for open loops (phase 195)."""

from __future__ import annotations

from typing import Any

from ze_agents.screen import (
    ResolveContext,
    ScreenLine,
    ScreenPosture,
    ScreenRef,
    ScreenResolver,
    as_utc,
    parse_uuid,
    resolve_each,
    sanitize_text,
    time_ago,
)


class LoopScreenResolver:
    kinds = frozenset({"loop"})

    def __init__(self, loop_store: Any) -> None:
        self._loops = loop_store

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        return await resolve_each(refs, lambda ref: self._load(ref, ctx))

    async def _load(self, ref: ScreenRef, ctx: ResolveContext) -> ScreenLine | None:
        loop_id = parse_uuid(ref.id)
        loop = await self._loops.get(loop_id) if loop_id else None
        if loop is None:
            return None
        parts = [str(getattr(loop.state, "value", loop.state))]
        if loop.drift_deadline:
            parts.append(
                f"drift deadline {time_ago(as_utc(loop.drift_deadline), ctx.now)}"
                if as_utc(loop.drift_deadline) <= ctx.now
                else f"drift deadline {as_utc(loop.drift_deadline).strftime('%Y-%m-%d')}"
            )
        if loop.drift_rationale:
            parts.append(sanitize_text(loop.drift_rationale, 100))
        if loop.reminder_id is not None:
            parts.append("has a reminder")
        if loop.goal_id is not None:
            parts.append("linked to a goal")
        return ScreenLine(
            ref=ref,
            label=loop.title,
            summary=", ".join(parts),
            posture=ScreenPosture(
                kind=loop.claim_kind,
                source=loop.provenance,
                confidence=loop.confidence,
                updated_at=as_utc(loop.updated_at),
            ),
        )


def build_screen_resolvers(*, loop_store: Any) -> list[ScreenResolver]:
    return [LoopScreenResolver(loop_store)]
