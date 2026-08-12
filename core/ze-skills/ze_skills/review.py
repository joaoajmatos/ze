from __future__ import annotations

from uuid import UUID

from ze_logging import get_logger

from ze_skills.errors import InvalidSkillTransitionError, SkillNotFoundError
from ze_skills.store import SkillStore
from ze_skills.types import Skill, SkillReview, SkillStatus

log = get_logger(__name__)


def _content_snapshot(skill: Skill) -> dict:
    return {
        "name": skill.name,
        "description": skill.description,
        "instructions": skill.instructions,
        "allowed_tools": skill.allowed_tools,
        "content_hash": skill.content_hash,
    }


async def approve_skill(store: SkillStore, skill_id: UUID) -> Skill:
    """Transition `pending_review -> active` (FR-006). Records a `SkillReview`
    row (`decision = approved`) with the current content snapshot (FR-016)."""
    skill = await store.get(skill_id)
    if skill is None:
        raise SkillNotFoundError(f"Skill {skill_id} not found")

    updated = await store.transition(
        skill_id, SkillStatus.PENDING_REVIEW, SkillStatus.ACTIVE, set_approved_at=True
    )
    if updated is None:
        raise InvalidSkillTransitionError(
            f"Cannot approve skill {skill_id}: not currently pending_review"
            f" (current status: {skill.status.value})"
        )

    await store.add_review(
        SkillReview(
            skill_id=skill_id,
            content_snapshot=_content_snapshot(skill),
            decision="approved",
        )
    )
    log.info("skill_approved", skill_id=str(skill_id))
    return updated


async def reject_skill(store: SkillStore, skill_id: UUID) -> Skill:
    """Transition `pending_review -> rejected` (FR-006). Records a
    `SkillReview` row (`decision = rejected`)."""
    skill = await store.get(skill_id)
    if skill is None:
        raise SkillNotFoundError(f"Skill {skill_id} not found")

    updated = await store.transition(
        skill_id, SkillStatus.PENDING_REVIEW, SkillStatus.REJECTED
    )
    if updated is None:
        raise InvalidSkillTransitionError(
            f"Cannot reject skill {skill_id}: not currently pending_review"
            f" (current status: {skill.status.value})"
        )

    await store.add_review(
        SkillReview(
            skill_id=skill_id,
            content_snapshot=_content_snapshot(skill),
            decision="rejected",
        )
    )
    log.info("skill_rejected", skill_id=str(skill_id))
    return updated
