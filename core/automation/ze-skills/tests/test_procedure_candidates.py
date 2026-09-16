from __future__ import annotations

from uuid import uuid4

from ze_skills.procedure_candidates import candidate_from_skill
from ze_skills.types import Skill, SkillSource


def test_imported_skill_candidate_does_not_change_allowed_tools() -> None:
    skill = Skill(
        id=uuid4(),
        name="Inbox triage",
        description="Clear the inbox",
        instructions="- Open inbox\n- Archive promotions",
        source=SkillSource.IMPORTED,
        allowed_tools=["search"],
    )
    candidate = candidate_from_skill(skill)
    assert candidate.source_kind.value == "skill"
    assert candidate.steps == ["Open inbox", "Archive promotions"]
    assert skill.allowed_tools == ["search"]
    assert not hasattr(candidate, "allowed_tools")
