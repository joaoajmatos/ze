from __future__ import annotations

import re
from dataclasses import dataclass

import yaml

from ze_skills.errors import SkillParseError

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)

# Agent Skills format convention: bundled executable scripts live under a
# `scripts/` directory and are referenced from the instructions body (markdown
# links, backtick paths) or declared explicitly via a `scripts:` frontmatter
# list. Neither is executable in this phase (FR-009) — detected, not run.
_SCRIPT_REF_RE = re.compile(
    r"scripts?/[^\s)\]`\"']+\.(?:py|sh|js|ts|rb|pl)", re.IGNORECASE
)


@dataclass
class ParsedSkill:
    """Result of parsing one `SKILL.md` document — not a stored entity. The
    caller (importer/bootstrap) attaches `source`/`origin_url`/`bundling_plugin`
    to build an actual `Skill`."""

    name: str
    description: str
    instructions: str
    allowed_tools: list[str] | None
    has_unsupported_scripts: bool


def parse_skill_md(text: str) -> ParsedSkill:
    """Parse a `SKILL.md` document: YAML frontmatter (name, description,
    optional `allowed-tools`) + free-text Markdown body, per the open Agent
    Skills format.

    Raises `SkillParseError` on malformed YAML or missing/empty required
    fields (FR-018).
    """
    if not text or not text.strip():
        raise SkillParseError("SKILL.md content is empty")

    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise SkillParseError(
            "SKILL.md must start with a YAML frontmatter block delimited by '---'"
        )

    frontmatter_text, body = match.group(1), match.group(2)

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as exc:
        raise SkillParseError(f"Malformed YAML frontmatter: {exc}") from exc

    if not isinstance(frontmatter, dict):
        raise SkillParseError("SKILL.md frontmatter must be a YAML mapping")

    name = frontmatter.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SkillParseError("SKILL.md frontmatter must declare a non-empty 'name'")

    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        raise SkillParseError(
            "SKILL.md frontmatter must declare a non-empty 'description'"
        )

    raw_allowed_tools = frontmatter.get("allowed-tools")
    allowed_tools: list[str] | None = None
    if raw_allowed_tools is not None:
        if not isinstance(raw_allowed_tools, list) or not all(
            isinstance(t, str) for t in raw_allowed_tools
        ):
            raise SkillParseError("'allowed-tools' must be a list of tool-name strings")
        allowed_tools = list(raw_allowed_tools)

    instructions = body.strip()

    raw_scripts = frontmatter.get("scripts")
    has_unsupported_scripts = bool(raw_scripts) or bool(
        _SCRIPT_REF_RE.search(instructions)
    )

    return ParsedSkill(
        name=name.strip(),
        description=description.strip(),
        instructions=instructions,
        allowed_tools=allowed_tools,
        has_unsupported_scripts=has_unsupported_scripts,
    )
