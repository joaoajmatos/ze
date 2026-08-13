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


def build_skill_matcher(store: SkillStore, embedder: Any, settings: Any) -> Any:
    """Construct the `SkillMatcher` injected into the orchestration graph's
    `config["configurable"]["skill_matcher"]` (consumed by the `match_skills` node)."""
    from ze_skills.matching import SkillMatcher

    skills_cfg = getattr(settings, "config", {}) or {}
    threshold_cfg = skills_cfg.get("skills", {}) if hasattr(skills_cfg, "get") else {}
    match_threshold = (
        threshold_cfg.get("match_threshold", 0.5)
        if hasattr(threshold_cfg, "get")
        else 0.5
    )
    return SkillMatcher(store=store, embedder=embedder, match_threshold=match_threshold)
