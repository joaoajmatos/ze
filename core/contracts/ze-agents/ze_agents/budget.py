"""Turn time budget for the conductor.

The conductor (companion) runs specialists inside its own wall-clock limit. A
soft deadline, kept before that limit by a reserve, lets the conductor stop
starting work and tell the user what was and was not done instead of timing out
in silence.
"""

from __future__ import annotations

import time
from typing import Any

from ze_agents.types import AgentContext
from ze_logging import get_logger

log = get_logger(__name__)

DEFAULT_BUDGET_SECONDS = 110
DEFAULT_RESERVE_SECONDS = 25

WRAP_UP_NOTE = (
    "The time budget for this turn is used up. Do not call any more tools. "
    "Answer now from what you already have: say what you finished, what you "
    "did not get to, and offer to continue it on the user's next message."
)

BUDGET_EXHAUSTED_ERROR = (
    "the time budget for this turn is used up; do not retry. Tell the user what "
    "is done, what is not, and offer to continue"
)


def _seconds(block: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(block.get(key, default))
    except (TypeError, ValueError):
        log.warning("conductor_budget_invalid", key=key, value=block.get(key))
        return default


def conductor_budget(config: dict[str, Any] | None) -> tuple[int, int]:
    """(budget_seconds, reserve_seconds) from the `conductor:` config block."""
    block = (config or {}).get("conductor") or {}
    budget = max(_seconds(block, "budget_seconds", DEFAULT_BUDGET_SECONDS), 1)
    reserve = _seconds(block, "reserve_seconds", DEFAULT_RESERVE_SECONDS)
    return budget, min(max(reserve, 0), budget - 1)


def set_soft_deadline(ctx: AgentContext, seconds: float) -> None:
    ctx.conductor.deadline = time.monotonic() + seconds


def has_budget(ctx: AgentContext) -> bool:
    return ctx.conductor.deadline is not None


def remaining_seconds(ctx: AgentContext) -> float | None:
    """Seconds left before the soft deadline; None when the turn has no budget."""
    deadline = ctx.conductor.deadline
    if deadline is None:
        return None
    return float(deadline) - time.monotonic()


def exhausted(ctx: AgentContext) -> bool:
    left = remaining_seconds(ctx)
    return left is not None and left <= 0


def partial_answer(ledger: list[dict[str, str]]) -> str:
    """Code-built reply for a conductor that hit its hard limit."""
    done = [e["agent"] for e in ledger if e.get("status") == "done"]
    open_ = [e["agent"] for e in ledger if e.get("status") != "done"]
    lines = ["I ran out of time on this one."]
    if done:
        lines.append(f"Finished: {', '.join(dict.fromkeys(done))}.")
    if open_:
        lines.append(
            f"Not finished (it may have partly run, so check before repeating): "
            f"{', '.join(dict.fromkeys(open_))}."
        )
    if not done and not open_:
        lines.append("I had not finished anything yet.")
    lines.append("Tell me to continue and I will pick it up from there.")
    return " ".join(lines)
