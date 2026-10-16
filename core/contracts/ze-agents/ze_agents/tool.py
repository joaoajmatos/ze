from __future__ import annotations

import asyncio
import inspect
import types
from dataclasses import dataclass
from enum import Enum
from typing import (
    Annotated,
    Any,
    Callable,
    Literal,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from ze_agents.errors import AgentConfigError, UnknownToolError
from ze_agents.reversibility import ToolReversibility

_tools: dict[str, ToolSpec] = {}

_PY_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


class _InjectedMarker:
    def __repr__(self) -> str:
        return "Injected"


_INJECTED = _InjectedMarker()
_T = TypeVar("_T")

Injected = Annotated[_T, _INJECTED]
"""Marks a tool parameter that Ze supplies and the model never sees.

`session_id: Injected[str | None] = None`. The parameter is left out of the
tool's schema, and a value the model sends for it is dropped before the call.
"""

_HIDDEN = object()


class _UnsupportedParam(Exception):
    pass


def _param_schema(annotation: Any) -> dict | object:
    """JSON schema for a model-visible type, or `_HIDDEN` for a dependency.

    Raises `_UnsupportedParam` for a data-shaped type JSON schema cannot express.
    """
    if annotation is inspect.Parameter.empty or annotation in (Any, object):
        return _HIDDEN
    origin = get_origin(annotation)
    if origin is Annotated:
        inner, *extras = get_args(annotation)
        if any(extra is _INJECTED for extra in extras):
            return _HIDDEN
        return _param_schema(inner)
    if origin in (Union, types.UnionType):
        members = [a for a in get_args(annotation) if a is not type(None)]
        schemas = [_param_schema(a) for a in members]
        if all(schema is _HIDDEN for schema in schemas):
            return _HIDDEN
        if len(schemas) == 1:
            return schemas[0]
        raise _UnsupportedParam(f"a union of several types ({annotation})")
    if origin is list:
        if not get_args(annotation):
            return {"type": "array"}
        (item,) = get_args(annotation)
        items = _param_schema(item)
        if items is _HIDDEN:
            raise _UnsupportedParam(f"list items of type {item!r}")
        return {"type": "array", "items": items}
    if origin is dict:
        key = (get_args(annotation) or (str,))[0]
        if key is not str:
            raise _UnsupportedParam("dict keys other than str")
        return {"type": "object"}
    if annotation in _PY_TO_JSON:
        return {"type": _PY_TO_JSON[annotation]}
    if (
        origin in (set, frozenset, tuple, Literal)
        or annotation in (set, frozenset, tuple, type(None))
        or (inspect.isclass(annotation) and issubclass(annotation, Enum))
    ):
        raise _UnsupportedParam(f"type {annotation!r}")
    return _HIDDEN


def _resolve_hints(func: Callable) -> dict[str, Any]:
    try:
        return get_type_hints(func, include_extras=True)
    except Exception:
        pass
    hints: dict[str, Any] = {}
    for name, param in inspect.signature(func).parameters.items():
        annotation = param.annotation
        if isinstance(annotation, str):
            try:
                annotation = eval(annotation, func.__globals__)  # noqa: S307
            except Exception:
                continue
        hints[name] = annotation
    return hints


def _build_parameters(name: str, func: Callable) -> tuple[dict, frozenset[str]]:
    """The model-visible parameters schema and the names of hidden parameters."""
    hints = _resolve_hints(func)
    properties: dict[str, Any] = {}
    required: list[str] = []
    hidden: set[str] = set()
    for param_name, param in inspect.signature(func).parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        try:
            schema = _param_schema(hints.get(param_name, inspect.Parameter.empty))
        except _UnsupportedParam as exc:
            raise AgentConfigError(
                f"Tool {name!r} parameter {param_name!r}: JSON schema cannot express "
                f"{exc}; change the type or mark it Injected[...]"
            ) from None
        if schema is _HIDDEN:
            hidden.add(param_name)
            continue
        properties[param_name] = schema
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
    params = {"type": "object", "properties": properties, "required": required}
    return params, frozenset(hidden)


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
            params, _ = _build_parameters(self.name, self.func)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": params,
            },
        }

    def hidden_params(self) -> frozenset[str]:
        """Parameters the model cannot set: `Injected[...]` ones and dependencies."""
        if self._schema_override is not None:
            return frozenset()
        _, hidden = _build_parameters(self.name, self.func)
        return hidden


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
        _build_parameters(name, func)
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
