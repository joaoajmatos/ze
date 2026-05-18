import inspect
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable

from ze.errors import UnknownToolError


class ToolAccess(str, Enum):
    READ  = "read"   # safe in any gate decision, including DRAFT
    WRITE = "write"  # suppressed when gate_decision is GateDecision.DRAFT


@dataclass(frozen=True)
class ToolParam:
    name:       str
    annotation: type
    required:   bool
    default:    Any = None


@dataclass(frozen=True)
class ToolSpec:
    name:        str
    fn:          Callable[..., Awaitable[Any]]
    access:      ToolAccess
    description: str
    params:      tuple[ToolParam, ...]


_tool_registry: dict[str, ToolSpec] = {}


def tool(*, access: ToolAccess | str, description: str) -> Callable:
    """Register an async function as a Ze tool.

    Args:
        access:      ToolAccess.READ or ToolAccess.WRITE
        description: One sentence — used in logs and future LLM tool schemas
    """
    def decorator(fn: Callable) -> Callable:
        spec = ToolSpec(
            name=fn.__name__,
            fn=fn,
            access=ToolAccess(access),
            description=description,
            params=_extract_params(fn),
        )
        _tool_registry[spec.name] = spec
        return fn
    return decorator


def get_tool(name: str) -> ToolSpec:
    """Return the ToolSpec for name, raising UnknownToolError if not registered."""
    if name not in _tool_registry:
        raise UnknownToolError(
            f"No tool registered: {name!r}. "
            f"Ensure the agent's tools module is imported at startup."
        )
    return _tool_registry[name]


def registered_tools() -> dict[str, ToolSpec]:
    """Return a snapshot of the full tool registry."""
    return dict(_tool_registry)


def _extract_params(fn: Callable) -> tuple[ToolParam, ...]:
    sig = inspect.signature(fn)
    hints = {}
    try:
        hints = inspect.get_annotations(fn, eval_str=True)
    except AttributeError:
        # Python < 3.10 fallback
        import typing
        hints = typing.get_type_hints(fn)

    params: list[ToolParam] = []
    for name, param in sig.parameters.items():
        if name in ("self", "return"):
            continue
        annotation = hints.get(name, Any)
        required = param.default is inspect.Parameter.empty
        default = None if required else param.default
        params.append(ToolParam(
            name=name,
            annotation=annotation,
            required=required,
            default=default,
        ))
    return tuple(params)
