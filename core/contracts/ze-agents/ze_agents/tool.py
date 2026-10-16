from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Literal, get_type_hints

from ze_agents.errors import AgentConfigError, UnknownToolError
from ze_agents.reversibility import ToolReversibility

_tools: dict[str, ToolSpec] = {}

_JSON_PRIMITIVE_TYPES = frozenset({str, int, float, bool, list, dict})

_PY_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


class ToolAccess(str, Enum):
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class AskDecision:
    """Outcome of a pre-call check: run the tool, ask the user first, or refuse."""

    kind: Literal["run", "ask", "refuse"]
    reason: str = ""
    message: str = ""
    result: Any = None  # structured tool result returned on refuse

    @classmethod
    def run(cls) -> AskDecision:
        return cls("run")

    @classmethod
    def ask(cls, reason: str = "") -> AskDecision:
        return cls("ask", reason=reason)

    @classmethod
    def refuse(cls, message: str, result: Any = None) -> AskDecision:
        return cls("refuse", message=message, result=result)


@dataclass
class ToolSpec:
    name: str
    access: ToolAccess
    description: str
    func: Callable
    _schema_override: dict | None = None
    constraint_gate: bool = False
    constraint_describe: Callable[[dict[str, Any]], Any] | None = None
    reversibility: ToolReversibility | None = None
    undo_tool: str | None = None
    undo_note: str | None = None
    effect_phrase: str | None = None
    asks_first: bool | None = None
    no_ask_reason: str | None = None
    ask_check: (
        Callable[[dict[str, Any], Any], AskDecision | Awaitable[AskDecision]] | None
    ) = None
    editable_field: str | None = None
    summarize: Callable[[dict[str, Any]], str | Awaitable[str | None] | None] | None = (
        None
    )

    def llm_schema(self) -> dict:
        if self._schema_override is not None:
            params = self._schema_override
        else:
            sig = inspect.signature(self.func)
            try:
                hints = get_type_hints(self.func)
            except Exception:
                hints = {}

            properties: dict[str, Any] = {}
            required: list[str] = []
            for param_name, param in sig.parameters.items():
                annotation = hints.get(param_name)
                if annotation not in _JSON_PRIMITIVE_TYPES:
                    continue
                properties[param_name] = {"type": _PY_TO_JSON[annotation]}
                if param.default is inspect.Parameter.empty:
                    required.append(param_name)
            params = {
                "type": "object",
                "properties": properties,
                "required": required,
            }

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": params,
            },
        }


def _check_declaration(
    name: str,
    access: ToolAccess,
    reversibility: ToolReversibility | None,
    undo_tool: str | None,
    undo_note: str | None,
    effect_phrase: str | None,
    asks_first: bool | None = None,
    no_ask_reason: str | None = None,
    ask_check: Callable | None = None,
    editable_field: str | None = None,
    summarize: Callable | None = None,
    func: Callable | None = None,
) -> bool | None:
    """Validate a declaration; return the resolved `asks_first`."""
    if access is ToolAccess.READ:
        if any(
            v is not None for v in (reversibility, undo_tool, undo_note, effect_phrase)
        ):
            raise AgentConfigError(f"READ tool {name!r} must not declare reversibility")
        if any(
            v is not None
            for v in (asks_first, no_ask_reason, ask_check, editable_field, summarize)
        ):
            raise AgentConfigError(
                f"READ tool {name!r} must not declare asks_first, no_ask_reason, "
                "ask_check, editable_field or summarize"
            )
        return None
    if reversibility is None:
        raise AgentConfigError(f"WRITE tool {name!r} must declare reversibility")
    if reversibility is ToolReversibility.REVERSIBLE:
        if not undo_tool or not undo_note:
            raise AgentConfigError(
                f"REVERSIBLE tool {name!r} must declare undo_tool and undo_note"
            )
    elif undo_tool is not None or undo_note is not None:
        raise AgentConfigError(
            f"IRREVERSIBLE tool {name!r} must not declare undo_tool or undo_note"
        )

    if asks_first is True:
        raise AgentConfigError(
            f"Tool {name!r}: asks_first=True is the IRREVERSIBLE default; omit it"
        )
    if reversibility is ToolReversibility.REVERSIBLE:
        if asks_first is not None:
            raise AgentConfigError(
                f"REVERSIBLE tool {name!r} must not declare asks_first"
            )
        if no_ask_reason is not None:
            raise AgentConfigError(
                f"REVERSIBLE tool {name!r} must not declare no_ask_reason"
            )
        resolved: bool | None = None
    elif asks_first is False:
        if not (no_ask_reason or "").strip():
            raise AgentConfigError(
                f"Tool {name!r} sets asks_first=False and needs a no_ask_reason"
            )
        resolved = False
    else:
        if no_ask_reason is not None:
            raise AgentConfigError(
                f"Tool {name!r} declares no_ask_reason without asks_first=False"
            )
        resolved = True

    if editable_field is not None and func is not None:
        if editable_field not in inspect.signature(func).parameters:
            raise AgentConfigError(
                f"Tool {name!r}: editable_field {editable_field!r} is not a parameter"
            )
    return resolved


def validate_tool_declarations() -> None:
    """Every `undo_tool` resolves to a registered WRITE tool and is not the tool itself."""
    for spec in _tools.values():
        if spec.undo_tool is None:
            continue
        if spec.undo_tool == spec.name:
            raise AgentConfigError(f"Tool {spec.name!r} cannot be its own undo_tool")
        target = _tools.get(spec.undo_tool)
        if target is None:
            raise AgentConfigError(
                f"Tool {spec.name!r} names unregistered undo_tool {spec.undo_tool!r}"
            )
        if target.access is not ToolAccess.WRITE:
            raise AgentConfigError(
                f"Tool {spec.name!r} undo_tool {spec.undo_tool!r} is not a WRITE tool"
            )


def tool(
    *,
    access: ToolAccess | str,
    description: str,
    constraint_gate: bool = False,
    constraint_describe: Callable[[dict[str, Any]], Any] | None = None,
    reversibility: ToolReversibility | str | None = None,
    undo_tool: str | None = None,
    undo_note: str | None = None,
    effect_phrase: str | None = None,
    asks_first: bool | None = None,
    no_ask_reason: str | None = None,
    ask_check: Callable[[dict[str, Any], Any], AskDecision | Awaitable[AskDecision]]
    | None = None,
    editable_field: str | None = None,
    summarize: Callable[[dict[str, Any]], str] | None = None,
) -> Callable:
    """Decorator that registers an async function as a Ze tool.

    WRITE tools must declare `reversibility`; READ tools must declare none of the
    reversibility arguments. A REVERSIBLE tool names its compensating `undo_tool`.
    An IRREVERSIBLE tool asks the user first unless it declares `asks_first=False`
    with a `no_ask_reason`.
    """
    access_val = ToolAccess(access) if isinstance(access, str) else access
    reversibility_val = (
        ToolReversibility(reversibility)
        if isinstance(reversibility, str)
        else reversibility
    )

    def _decorator(func: Callable) -> Callable:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError(f"Tool {func.__name__!r} must be an async function")
        name = func.__name__
        if name in _tools:
            raise AgentConfigError(f"Duplicate tool name {name!r}")
        resolved_asks_first = _check_declaration(
            name,
            access_val,
            reversibility_val,
            undo_tool,
            undo_note,
            effect_phrase,
            asks_first,
            no_ask_reason,
            ask_check,
            editable_field,
            summarize,
            func,
        )
        _tools[name] = ToolSpec(
            name=name,
            access=access_val,
            description=description,
            func=func,
            constraint_gate=constraint_gate,
            constraint_describe=constraint_describe,
            reversibility=reversibility_val,
            undo_tool=undo_tool,
            undo_note=undo_note,
            effect_phrase=effect_phrase,
            asks_first=resolved_asks_first,
            no_ask_reason=no_ask_reason,
            ask_check=ask_check,
            editable_field=editable_field,
            summarize=summarize,
        )
        return func

    return _decorator


def get_tool(name: str) -> ToolSpec:
    try:
        return _tools[name]
    except KeyError:
        raise UnknownToolError(f"No tool registered with name {name!r}")


def registered_tools() -> dict[str, ToolSpec]:
    return dict(_tools)


def clear_tool_registry() -> None:
    """Clear all registered tools. Intended for use in tests only."""
    _tools.clear()
