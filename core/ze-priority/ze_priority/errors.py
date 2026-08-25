from __future__ import annotations

from ze_agents.errors import ZeError


class ZePriorityError(ZeError):
    """All three PriorityView sources (loop, goal, hypothesis) failed to answer."""
