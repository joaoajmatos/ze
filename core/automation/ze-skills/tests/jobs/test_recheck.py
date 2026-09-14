from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from ze_skills.jobs.recheck import SkillRecheckJob
from ze_skills.types import Skill, SkillSource, SkillStatus


def _imported_skill(**overrides) -> Skill:
    defaults = dict(
        id=uuid4(),
        name="Pirate Speak",
        description="Ends every response with Arrr!",
        instructions="Always end with Arrr!",
        source=SkillSource.IMPORTED,
        origin_url="http://example.com/SKILL.md",
    )
    defaults.update(overrides)
    return Skill(**defaults)


async def test_sweeps_active_and_disabled_imported_skills():
    active = _imported_skill(status=SkillStatus.ACTIVE)
    disabled = _imported_skill(status=SkillStatus.DISABLED)
    store = AsyncMock()
    store.list = AsyncMock(return_value=[active, disabled])

    job = SkillRecheckJob(skill_store=store)
    with patch(
        "ze_skills.jobs.recheck.review.refresh_skill", AsyncMock()
    ) as refresh_mock:
        await job.run()

    store.list.assert_awaited_once_with(source=SkillSource.IMPORTED)
    assert refresh_mock.await_count == 2
    refresh_mock.assert_any_await(store, active.id)
    refresh_mock.assert_any_await(store, disabled.id)


async def test_per_skill_failure_does_not_abort_the_sweep():
    ok_skill = _imported_skill(status=SkillStatus.ACTIVE)
    failing_skill = _imported_skill(status=SkillStatus.ACTIVE)
    store = AsyncMock()
    store.list = AsyncMock(return_value=[failing_skill, ok_skill])

    job = SkillRecheckJob(skill_store=store)
    with patch(
        "ze_skills.jobs.recheck.review.refresh_skill",
        AsyncMock(side_effect=[RuntimeError("boom"), None]),
    ) as refresh_mock:
        await job.run()

    assert refresh_mock.await_count == 2


async def test_no_imported_skills_is_a_no_op():
    store = AsyncMock()
    store.list = AsyncMock(return_value=[])

    job = SkillRecheckJob(skill_store=store)
    with patch(
        "ze_skills.jobs.recheck.review.refresh_skill", AsyncMock()
    ) as refresh_mock:
        await job.run()

    refresh_mock.assert_not_awaited()
