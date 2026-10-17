"""Screen resolver for hypotheses (phase 195)."""

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
)


class HypothesisScreenResolver:
    kinds = frozenset({"hypothesis"})

    def __init__(self, hypothesis_store: Any) -> None:
        self._hypotheses = hypothesis_store

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        return await resolve_each(refs, self._load)

    async def _load(self, ref: ScreenRef) -> ScreenLine | None:
        hypothesis_id = parse_uuid(ref.id)
        hyp = await self._hypotheses.get(hypothesis_id) if hypothesis_id else None
        if hyp is None:
            return None
        relation = hyp.relation.replace("_", " ")
        evidence = len(hyp.evidence)
        confirmed = ", confirmed by you" if hyp.confirmed else ""
        return ScreenLine(
            ref=ref,
            label=sanitize_text(hyp.summary, 120),
            summary=f"{relation}, {evidence} piece{'s' if evidence != 1 else ''} of evidence{confirmed}",
            posture=ScreenPosture(
                kind=hyp.claim_kind,
                source="correlation",
                confidence=hyp.confidence,
                updated_at=as_utc(hyp.created_at),
            ),
        )


def build_screen_resolvers(*, hypothesis_store: Any) -> list[ScreenResolver]:
    return [HypothesisScreenResolver(hypothesis_store)]
