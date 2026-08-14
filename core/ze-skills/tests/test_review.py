from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from ze_skills import review
from ze_skills.errors import (
    InvalidSkillTransitionError,
    SkillNotFoundError,
    SkillParseError,
)
from ze_skills.importer import FetchedReferenceFile, FetchedSkill
from ze_skills.parser import ParsedSkill
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


@pytest.mark.asyncio
async def test_disable_skill_transitions_active_to_disabled():
    skill_id = uuid4()
    active = _skill(id=skill_id, status=SkillStatus.ACTIVE)
    disabled = _skill(id=skill_id, status=SkillStatus.DISABLED)
    store = AsyncMock()
    store.get = AsyncMock(return_value=active)
    store.transition = AsyncMock(return_value=disabled)

    result = await review.disable_skill(store, skill_id)

    assert result.status == SkillStatus.DISABLED
    store.transition.assert_awaited_once_with(
        skill_id, SkillStatus.ACTIVE, SkillStatus.DISABLED
    )
    store.add_review.assert_not_called()


@pytest.mark.asyncio
async def test_disable_skill_raises_invalid_transition_when_not_active():
    skill_id = uuid4()
    pending = _skill(id=skill_id, status=SkillStatus.PENDING_REVIEW)
    store = AsyncMock()
    store.get = AsyncMock(return_value=pending)
    store.transition = AsyncMock(return_value=None)

    with pytest.raises(InvalidSkillTransitionError):
        await review.disable_skill(store, skill_id)


@pytest.mark.asyncio
async def test_enable_skill_transitions_disabled_to_active_no_new_review():
    skill_id = uuid4()
    disabled = _skill(id=skill_id, status=SkillStatus.DISABLED)
    active = _skill(id=skill_id, status=SkillStatus.ACTIVE)
    store = AsyncMock()
    store.get = AsyncMock(return_value=disabled)
    store.transition = AsyncMock(return_value=active)

    result = await review.enable_skill(store, skill_id)

    assert result.status == SkillStatus.ACTIVE
    store.transition.assert_awaited_once_with(
        skill_id, SkillStatus.DISABLED, SkillStatus.ACTIVE
    )
    store.add_review.assert_not_called()


@pytest.mark.asyncio
async def test_enable_skill_rejected_when_drifted_to_pending_review():
    skill_id = uuid4()
    drifted = _skill(id=skill_id, status=SkillStatus.PENDING_REVIEW)
    store = AsyncMock()
    store.get = AsyncMock(return_value=drifted)
    store.transition = AsyncMock(return_value=None)

    with pytest.raises(InvalidSkillTransitionError):
        await review.enable_skill(store, skill_id)


@pytest.mark.asyncio
async def test_remove_skill_deletes_imported_skill():
    skill_id = uuid4()
    imported = _skill(id=skill_id, source=SkillSource.IMPORTED)
    store = AsyncMock()
    store.get = AsyncMock(return_value=imported)
    store.delete = AsyncMock(return_value=True)

    await review.remove_skill(store, skill_id)

    store.delete.assert_awaited_once_with(skill_id)


@pytest.mark.asyncio
async def test_remove_skill_rejects_bundled_skill():
    skill_id = uuid4()
    bundled = _skill(id=skill_id, source=SkillSource.BUNDLED, status=SkillStatus.ACTIVE)
    store = AsyncMock()
    store.get = AsyncMock(return_value=bundled)
    store.delete = AsyncMock()

    with pytest.raises(InvalidSkillTransitionError):
        await review.remove_skill(store, skill_id)

    store.delete.assert_not_called()


@pytest.mark.asyncio
async def test_remove_skill_raises_not_found_when_missing():
    store = AsyncMock()
    store.get = AsyncMock(return_value=None)

    with pytest.raises(SkillNotFoundError):
        await review.remove_skill(store, uuid4())


def _fetched(name="Pirate Speak", description="Ends with Arrr!", instructions="Arrr!"):
    return FetchedSkill(
        parsed=ParsedSkill(
            name=name,
            description=description,
            instructions=instructions,
            allowed_tools=None,
            has_unsupported_scripts=False,
        ),
        reference_files=[FetchedReferenceFile("notes.md", "notes", "text/markdown")],
    )


@pytest.mark.asyncio
async def test_refresh_skill_changed_content_reverts_to_pending_review():
    skill_id = uuid4()
    active = _skill(
        id=skill_id,
        status=SkillStatus.ACTIVE,
        origin_url="http://example.com/SKILL.md",
        instructions="Old instructions",
    )
    reverted = _skill(id=skill_id, status=SkillStatus.PENDING_REVIEW)
    store = AsyncMock()
    store.get = AsyncMock(return_value=active)
    store.apply_content_change = AsyncMock(return_value=reverted)
    store.delete_reference_files = AsyncMock()
    store.add_reference_file = AsyncMock()

    with patch.object(review, "fetch_skill_source", AsyncMock(return_value=_fetched())):
        result = await review.refresh_skill(store, skill_id)

    assert result.status == SkillStatus.PENDING_REVIEW
    store.apply_content_change.assert_awaited_once()
    kwargs = store.apply_content_change.call_args.kwargs
    assert kwargs["new_status"] == SkillStatus.PENDING_REVIEW
    store.delete_reference_files.assert_awaited_once_with(skill_id)
    store.add_reference_file.assert_awaited_once()
    store.mark_checked.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_skill_unchanged_content_no_status_change():
    skill_id = uuid4()
    fetched = _fetched()
    active = _skill(
        id=skill_id,
        status=SkillStatus.ACTIVE,
        origin_url="http://example.com/SKILL.md",
        name=fetched.parsed.name,
        description=fetched.parsed.description,
        instructions=fetched.parsed.instructions,
    )
    store = AsyncMock()
    store.get = AsyncMock(return_value=active)
    store.mark_checked = AsyncMock(return_value=active)

    with patch.object(review, "fetch_skill_source", AsyncMock(return_value=fetched)):
        result = await review.refresh_skill(store, skill_id)

    assert result.status == SkillStatus.ACTIVE
    store.mark_checked.assert_awaited_once_with(skill_id, error=None)
    store.apply_content_change.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_skill_unreachable_source_sets_check_error():
    skill_id = uuid4()
    active = _skill(
        id=skill_id, status=SkillStatus.ACTIVE, origin_url="http://example.com/SKILL.md"
    )
    store = AsyncMock()
    store.get = AsyncMock(return_value=active)
    store.mark_checked = AsyncMock(return_value=active)

    with patch.object(
        review,
        "fetch_skill_source",
        AsyncMock(side_effect=SkillParseError("Failed to fetch: connection refused")),
    ):
        result = await review.refresh_skill(store, skill_id)

    assert result.status == SkillStatus.ACTIVE
    store.mark_checked.assert_awaited_once()
    args, kwargs = store.mark_checked.call_args
    assert args[0] == skill_id
    assert "connection refused" in kwargs["error"]
    store.apply_content_change.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_skill_rejects_bundled_skill():
    skill_id = uuid4()
    bundled = _skill(id=skill_id, source=SkillSource.BUNDLED, status=SkillStatus.ACTIVE)
    store = AsyncMock()
    store.get = AsyncMock(return_value=bundled)

    with pytest.raises(InvalidSkillTransitionError):
        await review.refresh_skill(store, skill_id)


@pytest.mark.asyncio
async def test_refresh_skill_raises_not_found_when_missing():
    store = AsyncMock()
    store.get = AsyncMock(return_value=None)

    with pytest.raises(SkillNotFoundError):
        await review.refresh_skill(store, uuid4())
