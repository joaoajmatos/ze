"""ContextVar so execute_tool can inject LangGraph interrupt() without a ze-core import."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Callable

ToolInterruptFn = Callable[[dict[str, Any]], Any]

tool_interrupt_fn: ContextVar[ToolInterruptFn | None] = ContextVar(
    "tool_interrupt_fn", default=None
)
workspace_confirmed: ContextVar[bool] = ContextVar("workspace_confirmed", default=False)
workspace_run_origin: ContextVar[str] = ContextVar(
    "workspace_run_origin", default="conversation"
)
workspace_thread_id: ContextVar[str | None] = ContextVar(
    "workspace_thread_id", default=None
)
