"""Screen resolver for contacts (phase 195)."""

from __future__ import annotations

from typing import Any

from ze_sdk.screen import (
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


class ContactScreenResolver:
    kinds = frozenset({"contact"})

    def __init__(self, person_store: Any) -> None:
        self._people = person_store

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        return await resolve_each(refs, lambda ref: self._load(ref, ctx))

    async def _load(self, ref: ScreenRef, ctx: ResolveContext) -> ScreenLine | None:
        person_id = parse_uuid(ref.id)
        person = await self._people.get(person_id) if person_id else None
        if person is None:
            return None
        parts = [person.classification]
        if person.relationship_to_user:
            parts.append(sanitize_text(person.relationship_to_user, 60))
        if person.last_mentioned:
            parts.append(
                f"last mentioned {time_ago(as_utc(person.last_mentioned), ctx.now)}"
            )
        if not person.confirmed:
            parts.append("not yet confirmed by you")
        return ScreenLine(
            ref=ref,
            label=sanitize_text(person.name, 120),
            summary=", ".join(parts),
            posture=ScreenPosture(
                kind=person.claim_kind,
                source=str(getattr(person.provenance, "value", person.provenance)),
                confidence=person.confidence,
                updated_at=as_utc(person.updated_at),
            ),
        )


def build_screen_resolvers(*, person_store: Any) -> list[ScreenResolver]:
    return [ContactScreenResolver(person_store)]
