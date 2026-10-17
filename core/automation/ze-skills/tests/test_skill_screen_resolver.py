from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_agents.screen import ResolveContext, ScreenRef, ScreenStatus
from ze_skills.screen_resolvers import SkillScreenResolver
from ze_skills.types import Skill, SkillSource, SkillStatus

CTX = ResolveContext(now=datetime(2026, 10, 17, tzinfo=UTC))


async def test_skill_line_says_review_state_and_source():
    sid = uuid4()
    skill = Skill(
        name="trip-planner",
        description="d",
        instructions="i",
        source=SkillSource.IMPORTED,
        status=SkillStatus.PENDING_REVIEW,
        id=sid,
    )
    store = AsyncMock()
    store.get = AsyncMock(return_value=skill)
    [line] = await SkillScreenResolver(store).resolve(
        [ScreenRef(kind="skill", id=str(sid))], CTX
    )
    assert (
        line.label == "trip-planner"
        and line.summary == "pending review, imported skill"
    )
    store.get = AsyncMock(return_value=None)
    [gone] = await SkillScreenResolver(store).resolve(
        [ScreenRef(kind="skill", id=str(sid))], CTX
    )
    assert gone.status is ScreenStatus.MISSING
    store.get = AsyncMock(side_effect=RuntimeError("secret"))
    [bad] = await SkillScreenResolver(store).resolve(
        [ScreenRef(kind="skill", id=str(sid))], CTX
    )
    assert bad.status is ScreenStatus.FAILED and "secret" not in repr(bad)
