from __future__ import annotations

from typing import Any

from ze_agents.tool import ToolAccess, tool

from ze_skills.types import SkillStatus

_skill_store: Any = None


def configure(*, skill_store: Any) -> None:
    global _skill_store
    _skill_store = skill_store


@tool(
    access=ToolAccess.READ,
    description=(
        "List the skills currently active in this workspace — name, slug, "
        "description, and whether each has runnable scripts. Skills matched "
        "to the conversation are already injected into context automatically; "
        "use this when the user asks what skills exist, or before invoking "
        "one by name with workspace_run_skill_script."
    ),
)
async def list_skills() -> str:
    if _skill_store is None:
        return "Skill store is not available."
    skills = await _skill_store.list(status=SkillStatus.ACTIVE)
    if not skills:
        return "No active skills are installed."
    lines = []
    for skill in skills:
        scripts_note = " (has scripts)" if skill.has_scripts else ""
        lines.append(f"- {skill.name} (/{skill.slug}){scripts_note}: {skill.description}")
    return "\n".join(lines)
