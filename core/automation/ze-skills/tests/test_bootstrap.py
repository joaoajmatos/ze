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


def test_build_skill_matcher_takes_client_and_parses_surface():
    from ze_skills.bootstrap import build_skill_matcher

    class _Settings:
        config = {
            "skills": {"match_threshold": 0.55},
            "system_one": {
                "surfaces": {
                    "skills": {
                        "enabled": True,
                        "choice_trust": 0.7,
                        "needs_skill_hold": 0.5,
                        "shortlist_k": 6,
                    }
                }
            },
        }

    client = object()
    matcher = build_skill_matcher(AsyncMock(), object(), _Settings(), client)

    assert matcher._system_one is client
    assert matcher._surface.calibrated and matcher._surface.shortlist_k == 6
    assert matcher._threshold == 0.55


def test_build_skill_matcher_defaults_surface_off():
    from ze_skills.bootstrap import build_skill_matcher

    matcher = build_skill_matcher(AsyncMock(), object(), object())

    assert matcher._system_one is None and not matcher._surface.enabled
