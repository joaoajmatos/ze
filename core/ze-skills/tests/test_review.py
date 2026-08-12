from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ze_skills import review
from ze_skills.errors import InvalidSkillTransitionError, SkillNotFoundError
from ze_skills.types import Skill, SkillSource, SkillStatus


def _skill(status=SkillStatus.PENDING_REVIEW, **overrides) -> Skill:
    defaults = dict(
        id=uuid4(),
        name="Pirate Speak",
        description="Ends every response with Arrr!",
        instructions="Always end with Arrr!",
        source=SkillSource.IMPORTED,
        status=status,
    )
    defaults.update(overrides)
    return Skill(**defaults)


@pytest.mark.asyncio
async def test_approve_skill_transitions_pending_to_active():
    skill_id = uuid4()
    pending = _skill(id=skill_id, status=SkillStatus.PENDING_REVIEW)
    active = _skill(id=skill_id, status=SkillStatus.ACTIVE)
    store = AsyncMock()
    store.get = AsyncMock(return_value=pending)
    store.transition = AsyncMock(return_value=active)
    store.add_review = AsyncMock()

    result = await review.approve_skill(store, skill_id)

    assert result.status == SkillStatus.ACTIVE
    store.transition.assert_awaited_once_with(
        skill_id, SkillStatus.PENDING_REVIEW, SkillStatus.ACTIVE, set_approved_at=True
    )
    store.add_review.assert_awaited_once()
    review_arg = store.add_review.call_args.args[0]
    assert review_arg.decision == "approved"
    assert review_arg.skill_id == skill_id


@pytest.mark.asyncio
async def test_reject_skill_transitions_pending_to_rejected():
    skill_id = uuid4()
    pending = _skill(id=skill_id, status=SkillStatus.PENDING_REVIEW)
    rejected = _skill(id=skill_id, status=SkillStatus.REJECTED)
    store = AsyncMock()
    store.get = AsyncMock(return_value=pending)
    store.transition = AsyncMock(return_value=rejected)
    store.add_review = AsyncMock()

    result = await review.reject_skill(store, skill_id)

    assert result.status == SkillStatus.REJECTED
    review_arg = store.add_review.call_args.args[0]
    assert review_arg.decision == "rejected"


@pytest.mark.asyncio
async def test_approve_skill_raises_not_found_when_missing():
    store = AsyncMock()
    store.get = AsyncMock(return_value=None)

    with pytest.raises(SkillNotFoundError):
        await review.approve_skill(store, uuid4())


@pytest.mark.asyncio
async def test_approve_skill_raises_invalid_transition_when_not_pending():
    skill_id = uuid4()
    already_active = _skill(id=skill_id, status=SkillStatus.ACTIVE)
    store = AsyncMock()
    store.get = AsyncMock(return_value=already_active)
    store.transition = AsyncMock(return_value=None)

    with pytest.raises(InvalidSkillTransitionError):
        await review.approve_skill(store, skill_id)


@pytest.mark.asyncio
async def test_reject_skill_raises_invalid_transition_when_not_pending():
    skill_id = uuid4()
    already_rejected = _skill(id=skill_id, status=SkillStatus.REJECTED)
    store = AsyncMock()
    store.get = AsyncMock(return_value=already_rejected)
    store.transition = AsyncMock(return_value=None)

    with pytest.raises(InvalidSkillTransitionError):
        await review.reject_skill(store, skill_id)


@pytest.mark.asyncio
async def test_reject_skill_raises_not_found_when_missing():
    store = AsyncMock()
    store.get = AsyncMock(return_value=None)

    with pytest.raises(SkillNotFoundError):
        await review.reject_skill(store, uuid4())
