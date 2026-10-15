from __future__ import annotations

from ze_agents.errors import ZeError


class PushPolicyError(ZeError):
    """A push was declared or sent in a way the governor forbids."""


class CatchUpError(ZeError):
    """Catch-up could not compute a missed fire time."""
