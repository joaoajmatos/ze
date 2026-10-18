"""Programmatic tool use: the contract between the agentic loop and a script runner."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from ze_agents.errors import AgentError
from ze_logging import get_logger

logger = get_logger(__name__)

SCRIPT_TOOL_NAME = "run_tool_script"

SCRIPT_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": SCRIPT_TOOL_NAME,
        "description": (
            "Run a short Python script that calls your read tools through the "
            "ze_tools module and returns only what the answer needs. Use it for "
            "three or more reads, loops, joins or counting. Call "
            "finish(result, writes=[propose(tool, **args), ...]) at the end; "
            "writes run after the script under the usual confirmation rules. "
            "Give either source or procedure_id."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Python 3.12 source"},
                "procedure_id": {
                    "type": "string",
                    "description": "id of an approved script procedure to rerun",
                },
            },
        },
    },
}

SCRIPT_GUIDANCE = (
    "## Tool scripts\n"
    "For three or more reads, loops, joins or counting, write one script with "
    f"{SCRIPT_TOOL_NAME} instead of calling the read tools one by one. In the "
    "script, `import ze_tools as z` and call the read tools as functions with "
    "keyword arguments. Tool results are JSON data (dicts, lists, strings), so "
    "inspect keys defensively. Print nothing: stdout is discarded. End with "
    "`z.finish(result)` and return only what the answer needs. To change "
    "something, pass `writes=[z.propose(tool, **args)]` to finish; proposed writes "
    "run after the script under the normal confirmation rules. If the script fails, "
    "the error shows the shape of the last result; fix the script and run it again."
)

ScriptStatus = Literal[
    "ok",
    "exception",
    "timeout",
    "killed",
    "bad_request",
    "busy",
    "unavailable",
    "resource_limit",
]

_CONFIG_FIELDS: dict[str, type] = {
    "wall_seconds": int,
    "max_inner_calls": int,
    "max_proposed_writes": int,
    "max_spend_usd": float,
    "max_result_chars": int,
    "max_source_chars": int,
}


@dataclass(frozen=True)
class ScriptLimits:
    wall_seconds: int = 30
    max_inner_calls: int = 20
    max_proposed_writes: int = 10
    max_spend_usd: float = 0.05
    max_result_chars: int = 4000
    max_source_chars: int = 8000
    max_request_bytes: int = 262144
    max_reply_bytes: int = 1048576
    inner_result_store_chars: int = 2000

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> ScriptLimits:
        """Read `workspace.scripts`; a wrong type or non-positive value falls back."""
        workspace = (config or {}).get("workspace")
        block = workspace.get("scripts") if isinstance(workspace, dict) else None
        if not isinstance(block, dict):
            return cls()
        values: dict[str, Any] = {}
        for name, kind in _CONFIG_FIELDS.items():
            if name not in block:
                continue
            raw = block[name]
            ok = (
                not isinstance(raw, bool)
                and isinstance(raw, (int, float) if kind is float else int)
                and raw > 0
            )
            if not ok:
                logger.warning("script_limit_invalid", field=name, value=repr(raw))
                continue
            values[name] = kind(raw)
        return cls(**values)


@dataclass(frozen=True)
class ScriptRequest:
    seq: int
    tool: str
    args: dict[str, Any]


@dataclass(frozen=True)
class DispatchReply:
    ok: bool
    value: Any = None
    error: str | None = None
    stop: bool = False


@dataclass
class ScriptOutcome:
    status: ScriptStatus
    value: Any = None
    writes: list[dict[str, Any]] = field(default_factory=list)
    stderr_tail: str = ""
    exception: str | None = None


class ScriptRunner(Protocol):
    async def run(
        self,
        *,
        script_id: str,
        agent: str,
        source: str,
        stub: str,
        limits: ScriptLimits,
        dispatch: Callable[[ScriptRequest], Awaitable[DispatchReply]],
        procedure_id: str | None = None,
    ) -> ScriptOutcome: ...


@dataclass
class ScriptBudget:
    limit_usd: float
    spent_usd: float = 0.0

    @property
    def exhausted(self) -> bool:
        return self.spent_usd >= self.limit_usd


current_script_budget: ContextVar[ScriptBudget | None] = ContextVar(
    "current_script_budget", default=None
)

in_script_call: ContextVar[bool] = ContextVar("in_script_call", default=False)


def charge_script(usd: float) -> None:
    """Add a model call's estimated cost to the active script budget, if any."""
    budget = current_script_budget.get()
    if budget is not None:
        budget.spent_usd += usd


class ScriptError(AgentError):
    """A script could not run or ended on a limit; `kind` is the model-facing code."""

    def __init__(self, kind: str, message: str = "") -> None:
        super().__init__(message or kind)
        self.kind = kind
