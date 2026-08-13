from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ze_logging import get_logger

from ze_skills.parser import parse_skill_md
from ze_skills.store import PostgresSkillStore, SkillStore
from ze_skills.types import Skill, SkillSource, SkillStatus

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


async def register_bundled_skills(store: SkillStore, plugins: list[Any]) -> None:
    """Load each plugin's `bundled_skill_paths()` and register them with
    `SkillStore` as `source=bundled`, `status=active` — no review gate, since
    these ship with (and are trusted at the level of) the plugin itself
    (FR-007). Idempotent: re-running against an already-registered bundled
    skill is a no-op, matched on the `(slug, source)` uniqueness constraint.
    """
    for plugin in plugins:
        paths = plugin.bundled_skill_paths()
        if not paths:
            continue
        plugin_name = type(plugin).__name__
        for path in paths:
            text = Path(path).read_text()
            parsed = parse_skill_md(text)
            skill = Skill(
                name=parsed.name,
                description=parsed.description,
                instructions=parsed.instructions,
                source=SkillSource.BUNDLED,
                bundling_plugin=plugin_name,
                allowed_tools=parsed.allowed_tools,
                has_unsupported_scripts=parsed.has_unsupported_scripts,
                status=SkillStatus.ACTIVE,
            )
            existing = await store.get_by_slug_source(skill.slug, SkillSource.BUNDLED)
            if existing is not None:
                log.debug(
                    "bundled_skill_already_registered",
                    slug=skill.slug,
                    plugin=plugin_name,
                )
                continue
            created = await store.create(skill)
            log.info(
                "bundled_skill_registered",
                skill_id=str(created.id),
                slug=created.slug,
                plugin=plugin_name,
            )
