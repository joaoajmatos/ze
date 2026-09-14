from __future__ import annotations

from ze_agents.errors import ZeError


class ZePriorityError(ZeError):
    """All three PriorityView sources (loop, goal, hypothesis) failed to answer."""


class PriorityOverrideNotFoundError(ZePriorityError):
    """No active `PriorityOverride` row matches the given id."""


class StaleReprioritizationTargetError(ZePriorityError):
    """The reprioritization target or anchor no longer exists in any `PriorityView`
    source list (FR-011)."""
