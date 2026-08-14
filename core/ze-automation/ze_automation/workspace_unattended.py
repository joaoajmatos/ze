"""Unattended workspace gating helpers. Duck-typed — no ze_workspace import."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from ze_agents.interrupt import workspace_run_origin

_UNATTENDED_ACTIONS = ("run", "run_script", "write")


def consult_unattended(
    gate: Any,
    *,
    mode: Any,
    action: str,
    origin: str = "unattended",
) -> str:
    """Ask an injected gate whether an unattended workspace action may proceed."""
    decide = getattr(gate, "decide_named", None) or gate.decide
    decision = decide(mode=mode, action=action, origin=origin)
    return str(getattr(decision, "value", decision))


@asynccontextmanager
async def unattended_workspace(
    gate: Any | None,
    get_mode: Callable[[], Awaitable[Any]] | None,
) -> AsyncIterator[dict[str, str]]:
    """Mark this task as origin=unattended and consult the gate before tools run."""
    decisions: dict[str, str] = {}
    if gate is not None and get_mode is not None:
        mode = await get_mode()
        for action in _UNATTENDED_ACTIONS:
            decisions[action] = consult_unattended(gate, mode=mode, action=action)
    token = workspace_run_origin.set("unattended")
    try:
        yield decisions
    finally:
        workspace_run_origin.reset(token)
