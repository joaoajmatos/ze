from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class CostContext:
    flow_type: str
    agent: str
    session_id: str | None = None


_TURN_REPLACEABLE = frozenset({"unknown", "user_message"})
_CTX: ContextVar[CostContext | None] = ContextVar("ze_cost_ctx", default=None)


def set_flow_context(flow_type: str, session_id: str | None = None) -> None:
    current = _CTX.get()
    if current is not None:
        _CTX.set(replace(current, flow_type=flow_type, session_id=session_id))
    else:
        _CTX.set(
            CostContext(flow_type=flow_type, agent="unknown", session_id=session_id)
        )


def start_flow_context(flow_type: str, session_id: str | None = None) -> None:
    """Begin a new flow with a clean context, so nothing from an earlier flow leaks in."""
    _CTX.set(CostContext(flow_type=flow_type, agent="unknown", session_id=session_id))


def enter_turn_context(thread_id: str) -> None:
    """Attribute a conversation turn to its thread unless an outer flow (eval, workflow) already owns the context."""
    current = _CTX.get()
    if current is not None and current.flow_type not in _TURN_REPLACEABLE:
        return
    start_flow_context("user_message", session_id=thread_id)


def set_agent_context(agent: str) -> None:
    current = _CTX.get()
    if current is not None:
        _CTX.set(replace(current, agent=agent))
    else:
        _CTX.set(CostContext(flow_type="unknown", agent=agent))


def get_cost_context() -> CostContext:
    return _CTX.get() or CostContext(flow_type="unknown", agent="unknown")
