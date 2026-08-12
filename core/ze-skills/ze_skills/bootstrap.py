from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ze_logging import get_logger

from ze_skills.store import PostgresSkillStore, SkillStore

log = get_logger(__name__)


@dataclass
class SkillsStack:
    skill_store: PostgresSkillStore
    pool: Any
    deps: dict[type, Any] = field(default_factory=dict)


def build_skills_stack(shared: Any, settings: Any) -> SkillsStack:
    pool = shared.pool
    skill_store = PostgresSkillStore(pool=pool)

    deps: dict[type, Any] = {
        SkillStore: skill_store,
        PostgresSkillStore: skill_store,
    }

    return SkillsStack(skill_store=skill_store, pool=pool, deps=deps)
