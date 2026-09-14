from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ze_skills.bootstrap import register_bundled_skills
from ze_skills.types import Skill, SkillSource, SkillStatus

_SKILL_MD = """---
name: Pirate Speak
description: Ends every response with "Arrr!"
---

Always end every response with "Arrr!"
"""


class _FakePlugin:
    def __init__(self, paths: list[str]) -> None:
        self._paths = paths

    def bundled_skill_paths(self) -> list[str]:
        return self._paths


@pytest.mark.asyncio
async def test_register_bundled_skills_creates_new_skill(tmp_path):
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text(_SKILL_MD)
    store = AsyncMock()
    store.get_by_slug_source = AsyncMock(return_value=None)
    store.create = AsyncMock(
        return_value=Skill(
            name="Pirate Speak",
            description="desc",
            instructions="instructions",
            source=SkillSource.BUNDLED,
            status=SkillStatus.ACTIVE,
        )
    )

    await register_bundled_skills(store, [_FakePlugin([str(skill_path)])])

    store.create.assert_awaited_once()
    created_skill = store.create.call_args.args[0]
    assert created_skill.source == SkillSource.BUNDLED
    assert created_skill.status == SkillStatus.ACTIVE
    assert created_skill.bundling_plugin == "_FakePlugin"


@pytest.mark.asyncio
async def test_register_bundled_skills_idempotent_skips_existing(tmp_path):
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text(_SKILL_MD)
    existing = Skill(
        name="Pirate Speak",
        description="desc",
        instructions="instructions",
        source=SkillSource.BUNDLED,
        status=SkillStatus.ACTIVE,
    )
    store = AsyncMock()
    store.get_by_slug_source = AsyncMock(return_value=existing)
    store.create = AsyncMock()

    await register_bundled_skills(store, [_FakePlugin([str(skill_path)])])

    store.create.assert_not_called()


@pytest.mark.asyncio
async def test_register_bundled_skills_noop_when_no_paths():
    store = AsyncMock()
    store.create = AsyncMock()

    await register_bundled_skills(store, [_FakePlugin([])])

    store.create.assert_not_called()
