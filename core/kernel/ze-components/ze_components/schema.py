from __future__ import annotations

import dataclasses
import types
import typing

_PY_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}

_KNOWN_TYPES = frozenset([str, int, float, bool, list, dict, type(None)])


def _union_args(annotation: type) -> tuple[type, ...]:
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        return typing.get_args(annotation)
    return ()


def _unwrap_optional(annotation: type) -> tuple[type, bool]:
    args = _union_args(annotation)
    if args and type(None) in args:
        non_none = [a for a in args if a is not type(None)]
        if not non_none:
            return str, True
        if len(non_none) == 1:
            return non_none[0], True
        return typing.Union[tuple(non_none)], True  # type: ignore[return-value]
    return annotation, False


def _is_action_union(annotation: type) -> bool:
    from ze_components.actions import ACTION_TYPES

    args = _union_args(annotation)
    return bool(args) and set(args) == set(ACTION_TYPES)


def _scalar_union_schema(annotation: type) -> dict | None:
    args = _union_args(annotation)
    if args and all(a in _PY_TO_JSON for a in args):
        names = {"integer": "number"}
        kinds = sorted({names.get(_PY_TO_JSON[a], _PY_TO_JSON[a]) for a in args})
        return {"type": kinds}
    return None


def _mentions_action(annotation: type, seen: frozenset[type] = frozenset()) -> bool:
    """True when a field's type is, or holds, a typed action. Models never write those."""
    from ze_components.actions import ACTION_TYPES

    if annotation in ACTION_TYPES:
        return True
    if dataclasses.is_dataclass(annotation) and isinstance(annotation, type):
        if annotation in seen:
            return False
        hints = typing.get_type_hints(annotation)
        return any(
            _mentions_action(hints[f.name], seen | {annotation})
            for f in dataclasses.fields(annotation)
            if f.init
        )
    return any(_mentions_action(a, seen) for a in typing.get_args(annotation))


def _literal_schema(annotation: type) -> dict | None:
    if typing.get_origin(annotation) is typing.Literal:
        values = typing.get_args(annotation)
        if len(values) == 1:
            return {"const": values[0]}
        return {"enum": list(values)}
    return None


# Posture is set by code from the owning record, never by the model.
_MODEL_OMITTED_FIELDS = frozenset({"claim"})


def _field_schema(annotation: type) -> dict:
    """Convert a single type annotation to a JSON schema fragment."""
    literal = _literal_schema(annotation)
    if literal is not None:
        return literal

    annotation, _ = _unwrap_optional(annotation)
    literal = _literal_schema(annotation)
    if literal is not None:
        return literal

    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    scalar_union = _scalar_union_schema(annotation)
    if scalar_union is not None:
        return scalar_union

    if annotation in _PY_TO_JSON:
        return {"type": _PY_TO_JSON[annotation]}

    if origin is list:
        item_type = args[0] if args else str
        return {"type": "array", "items": _field_schema(item_type)}

    if origin is dict:
        value_type = args[1] if len(args) > 1 else str
        return {"type": "object", "additionalProperties": _field_schema(value_type)}

    if dataclasses.is_dataclass(annotation):
        return _dataclass_schema(annotation)

    return {"type": "string"}


def _dataclass_schema(cls: type) -> dict:
    """Build a JSON schema object from a dataclass."""
    hints = typing.get_type_hints(cls)
    props: dict = {}
    required: list[str] = []
    for f in dataclasses.fields(cls):
        if not f.init or f.name in _MODEL_OMITTED_FIELDS:
            continue
        if _mentions_action(hints[f.name]):
            continue
        props[f.name] = {
            **_field_schema(hints[f.name]),
            **f.metadata.get("json_schema", {}),
        }
        if (
            f.default is dataclasses.MISSING
            and f.default_factory is dataclasses.MISSING  # type: ignore[misc]
        ):
            required.append(f.name)
    schema: dict = {
        "type": "object",
        "properties": props,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def _discriminator_value(cls: type, name: str = "type") -> str | None:
    hints = typing.get_type_hints(cls)
    for f in dataclasses.fields(cls):
        if f.init or f.name != name:
            continue
        literal = _literal_schema(hints.get(name, str))
        if literal and "const" in literal:
            return literal["const"]
    return None


def _export_field_schema(
    annotation: type,
    *,
    field_name: str = "",
    primitive_ref: dict | None = None,
) -> dict:
    literal = _literal_schema(annotation)
    if literal is not None:
        return literal

    annotation, _ = _unwrap_optional(annotation)
    literal = _literal_schema(annotation)
    if literal is not None:
        return literal

    if field_name == "children" and primitive_ref is not None:
        return {"type": "array", "items": primitive_ref}

    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    if _is_action_union(annotation):
        return {"$ref": "#/$defs/PrimitiveAction"}

    scalar_union = _scalar_union_schema(annotation)
    if scalar_union is not None:
        return scalar_union

    if annotation in _PY_TO_JSON:
        return {"type": _PY_TO_JSON[annotation]}

    if origin is list:
        item_type = args[0] if args else str
        if dataclasses.is_dataclass(item_type):
            return {
                "type": "array",
                "items": {"$ref": f"#/$defs/{item_type.__name__}"},
            }
        return {"type": "array", "items": _export_field_schema(item_type)}

    if origin is dict:
        value_type = args[1] if len(args) > 1 else str
        return {
            "type": "object",
            "additionalProperties": _export_field_schema(value_type),
        }

    if dataclasses.is_dataclass(annotation):
        return {"$ref": f"#/$defs/{annotation.__name__}"}

    return {"type": "string"}


def _export_dataclass_schema(
    cls: type,
    *,
    primitive_ref: dict | None = None,
    include_discriminator: bool = False,
    discriminator_field: str = "type",
) -> dict:
    hints = typing.get_type_hints(cls)
    props: dict = {}
    required: list[str] = []
    for f in dataclasses.fields(cls):
        if not f.init and not (include_discriminator and f.name == discriminator_field):
            continue
        props[f.name] = {
            **_export_field_schema(
                hints[f.name],
                field_name=f.name,
                primitive_ref=primitive_ref,
            ),
            **f.metadata.get("json_schema", {}),
        }
        if (
            f.default is dataclasses.MISSING
            and f.default_factory is dataclasses.MISSING  # type: ignore[misc]
        ) or (include_discriminator and f.name == discriminator_field):
            required.append(f.name)
    schema: dict = {
        "type": "object",
        "properties": props,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def build_render_schema(component_cls: type) -> dict:
    """Build the JSON schema parameters block for a render tool whose arguments
    match the component dataclass fields (excluding `type`)."""
    return _dataclass_schema(component_cls)


def export_json_schema() -> dict:
    """Generate a full JSON schema document with $defs for all primitive types."""
    from ze_components import PRIMITIVE_TYPES, PRIMITIVE_SUB_TYPES
    from ze_components.actions import ACTION_TYPES

    primitive_ref = {"$ref": "#/$defs/Primitive"}
    defs: dict = {}

    action_mapping: dict[str, str] = {}
    for cls in PRIMITIVE_SUB_TYPES:
        if cls in ACTION_TYPES:
            defs[cls.__name__] = _export_dataclass_schema(
                cls, include_discriminator=True, discriminator_field="kind"
            )
            action_mapping[_discriminator_value(cls, "kind")] = (
                f"#/$defs/{cls.__name__}"
            )
        else:
            defs[cls.__name__] = _export_dataclass_schema(cls)

    defs["PrimitiveAction"] = {
        "oneOf": [{"$ref": f"#/$defs/{cls.__name__}"} for cls in ACTION_TYPES],
        "discriminator": {"propertyName": "kind", "mapping": action_mapping},
    }

    discriminator_mapping: dict[str, str] = {}
    for cls in PRIMITIVE_TYPES:
        defs[cls.__name__] = _export_dataclass_schema(
            cls,
            primitive_ref=primitive_ref,
            include_discriminator=True,
        )
        discriminator = _discriminator_value(cls)
        if discriminator is not None:
            discriminator_mapping[discriminator] = f"#/$defs/{cls.__name__}"

    defs["Primitive"] = {
        "oneOf": [{"$ref": f"#/$defs/{cls.__name__}"} for cls in PRIMITIVE_TYPES],
        "discriminator": {
            "propertyName": "type",
            "mapping": discriminator_mapping,
        },
    }
    defs["PrimitiveTree"] = {
        "type": "array",
        "items": primitive_ref,
        "minItems": 1,
    }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Ze UI Primitives",
        "$defs": defs,
        "oneOf": [{"$ref": f"#/$defs/{cls.__name__}"} for cls in PRIMITIVE_TYPES],
        "discriminator": {
            "propertyName": "type",
            "mapping": discriminator_mapping,
        },
    }
