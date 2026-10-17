"""Screen resolver for skills (phase 195)."""

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
)
from ze_skills.types import SkillStatus

_STATUS_WORDS = {
    SkillStatus.PENDING_REVIEW: "pending review",
    SkillStatus.ACTIVE: "approved",
    SkillStatus.DISABLED: "disabled",
    SkillStatus.REJECTED: "rejected",
}


class SkillScreenResolver:
    kinds = frozenset({"skill"})

    def __init__(self, skill_store: Any) -> None:
        self._skills = skill_store

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        return await resolve_each(refs, self._load)

    async def _load(self, ref: ScreenRef) -> ScreenLine | None:
        skill_id = parse_uuid(ref.id)
        skill = await self._skills.get(skill_id) if skill_id else None
        if skill is None:
            return None
        status = _STATUS_WORDS.get(skill.status, str(skill.status))
        return ScreenLine(
            ref=ref,
            label=skill.name,
            summary=f"{status}, {str(getattr(skill.source, 'value', skill.source))} skill",
            posture=ScreenPosture(
                source="skill", updated_at=as_utc(skill.approved_at or skill.created_at)
            ),
        )


def build_screen_resolvers(*, skill_store: Any) -> list[ScreenResolver]:
    return [SkillScreenResolver(skill_store)]
