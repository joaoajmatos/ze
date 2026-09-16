"""Platform tool: explicit procedure invocation. Matching never executes steps."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from ze_agents.tool import ToolAccess, tool
from ze_agents.types import AgentContext
from ze_logging import get_logger

from ze_memory.procedures.errors import (
    BlockedProcedureError,
    IneligibleProcedureError,
)
from ze_memory.procedures.types import MatchState, ProcedureInvocationOrigin

log = get_logger(__name__)

INVOKE_PROCEDURE_TOOL = "invoke_procedure"

_activator: Any = None


def configure(*, activator: Any) -> None:
    global _activator
    _activator = activator


@tool(
    access=ToolAccess.READ,
    description=(
        "Explicitly invoke a ready procedure by id. This records the version to "
        "follow; it does not run any steps. Call this before acting on procedure "
        "guidance. Blocked or disabled procedures are rejected."
    ),
)
async def invoke_procedure(procedure_id: str, ctx: AgentContext | None = None) -> str:
    if ctx is None:
        return "[error: procedure invocation requires agent context]"
    if _activator is None:
        return "[error: procedure activation is unavailable]"
    matches = getattr(ctx, "procedure_matches", None) or []
    try:
        wanted = UUID(procedure_id)
    except ValueError:
        return "[error: procedure_id must be a UUID]"
    match = next((item for item in matches if item.procedure_id == wanted), None)
    if match is None:
        return "[error: procedure is not in the current ready/blocked matches]"
    if match.state is not MatchState.READY:
        return "[error: procedure is blocked; unmet preconditions remain]"
    try:
        invocation = await _activator.invoke(
            match,
            origin=ProcedureInvocationOrigin.AGENT,
            caller=getattr(ctx, "session_id", "agent"),
            task_context_ref=ctx.session_id,
        )
    except (BlockedProcedureError, IneligibleProcedureError) as exc:
        log.info("invoke_procedure_rejected", error=str(exc))
        return f"[error: {exc}]"
    ctx.procedure_invocation_id = str(invocation.id)
    ctx.procedure_invoked_id = str(match.procedure_id)
    ctx.procedure_invoked_version_id = str(match.version_id)
    ctx.procedure_tool_names = sorted(match.effective_tool_names)
    return (
        f"Invoked procedure {match.name} version {match.version_number}. "
        "Follow its steps using only the now-narrowed tools. "
        "The capability gate still applies to every action."
    )
