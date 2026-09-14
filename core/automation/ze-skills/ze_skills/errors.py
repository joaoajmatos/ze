from __future__ import annotations

from ze_agents.errors import ZeError


class SkillParseError(ZeError):
    """Import source failed to fetch or parse per the Agent Skills format
    (unreachable URL, malformed frontmatter, missing required fields)."""


class SkillNotFoundError(ZeError):
    """Unknown skill id on a read/transition request."""


class InvalidSkillTransitionError(ZeError):
    """Attempted status transition not permitted from the skill's current status."""
