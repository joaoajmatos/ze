"""Per-run ContextVars shared by the workspace tools and the engine."""

from __future__ import annotations

from contextvars import ContextVar

workspace_run_origin: ContextVar[str] = ContextVar(
    "workspace_run_origin", default="conversation"
)
workspace_thread_id: ContextVar[str | None] = ContextVar(
    "workspace_thread_id", default=None
)
