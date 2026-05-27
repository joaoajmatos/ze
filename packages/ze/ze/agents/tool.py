import inspect
import types
import typing
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Union

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


_JSON_PRIMITIVES = frozenset({str, int, float, bool, type(None)})


def _is_llm_visible(annotation: Any) -> bool:
    """Return True if annotation is a JSON-primitive type the LLM can supply."""
    if annotation is Any:
        return True
    if annotation in _JSON_PRIMITIVES:
        return True
    origin = getattr(annotation, "__origin__", None)
    # Handle Python 3.10+ X | Y union syntax
    if isinstance(annotation, types.UnionType):
        return all(_is_llm_visible(a) for a in annotation.__args__)
    # Handle typing.Union / Optional
    if origin is Union:
        return all(_is_llm_visible(a) for a in annotation.__args__)
    # Handle list[X] / List[X] / tuple[X]
    if origin in (list, tuple):
        args = getattr(annotation, "__args__", ()) or ()
        return all(_is_llm_visible(a) for a in args)
    # dict / Dict — treat as opaque object
    if origin is dict or annotation is dict:
        return True
    return False


def _to_json_type(annotation: Any) -> str:
    """Map a Python annotation to a JSON Schema type string."""
    if annotation is str or annotation is Any:
        return "string"
    if annotation is int:
        return "integer"
    if annotation is float:
        return "number"
    if annotation is bool:
        return "boolean"
    if annotation is dict:
        return "object"
    origin = getattr(annotation, "__origin__", None)
    if origin in (list, tuple):
        return "array"
    if origin is dict:
        return "object"
    # Union / Optional — use type of first non-None arg
    if isinstance(annotation, types.UnionType) or origin is Union:
        non_none = [a for a in annotation.__args__ if a is not type(None)]
        return _to_json_type(non_none[0]) if non_none else "string"
    return "string"


def _is_optional(annotation: Any) -> bool:
    """Return True if annotation is Optional[X] (i.e. can be None)."""
    origin = getattr(annotation, "__origin__", None)
    if isinstance(annotation, types.UnionType) or origin is Union:
        return type(None) in annotation.__args__
    return False


@dataclass(frozen=True)
class ToolSpec:
    name:        str
    fn:          Callable[..., Awaitable[Any]]
    access:      ToolAccess
    description: str
    params:      tuple[ToolParam, ...]

    def llm_schema(self) -> dict:
        """Return OpenAI-format function schema for this tool.

        Only JSON-primitive params are included; Ze-internal deps (e.g. client
        objects) are automatically excluded so the LLM never sees them.
        """
        properties: dict[str, dict] = {}
        required: list[str] = []

        for p in self.params:
            if not _is_llm_visible(p.annotation):
                continue
            prop: dict = {"type": _to_json_type(p.annotation)}
            properties[p.name] = prop
            if p.required and not _is_optional(p.annotation):
                required.append(p.name)

        schema: dict = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }


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
