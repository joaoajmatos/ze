from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, get_type_hints

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
) -> None:
    if access is ToolAccess.READ:
        if any(
            v is not None for v in (reversibility, undo_tool, undo_note, effect_phrase)
        ):
            raise AgentConfigError(f"READ tool {name!r} must not declare reversibility")
        return
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


_UNDO_SCALARS = (str, int, float, bool, type(None))


def is_valid_undo_payload(payload: Any) -> bool:
    """True for a dict whose values are scalars or lists of scalars."""
    if not isinstance(payload, dict):
        return False
    for value in payload.values():
        if isinstance(value, list):
            if not all(isinstance(v, _UNDO_SCALARS) for v in value):
                return False
        elif not isinstance(value, _UNDO_SCALARS):
            return False
    return True


def undo_payload(**kwargs: Any) -> dict[str, Any]:
    """Build the per-call undo payload a REVERSIBLE tool returns under `"undo"`.

    Values must be JSON scalars or lists of scalars: ids and names, never content.
    """
    for key, value in kwargs.items():
        if not is_valid_undo_payload({key: value}):
            raise AgentConfigError(
                f"undo_payload value for {key!r} must be a scalar or a list of scalars"
            )
    return dict(kwargs)


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
) -> Callable:
    """Decorator that registers an async function as a Ze tool.

    WRITE tools must declare `reversibility`; READ tools must declare none of the
    reversibility arguments. A REVERSIBLE tool names its compensating `undo_tool`.
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
        _check_declaration(
            name, access_val, reversibility_val, undo_tool, undo_note, effect_phrase
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
