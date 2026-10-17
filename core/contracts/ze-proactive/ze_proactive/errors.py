from __future__ import annotations

from ze_agents.errors import ZeError


class PushPolicyError(ZeError):
    """A push was declared or sent in a way the governor forbids."""


class BudgetUnavailableError(ZeError):
    """The attention budget cannot be read (no push log, or the store failed)."""


class CatchUpError(ZeError):
    """Catch-up could not compute a missed fire time."""
