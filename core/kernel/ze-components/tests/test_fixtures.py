"""Shared UI fixtures: every tree under packages/ze-ui/fixtures is checked against its `.expect.json`.

An expectation is `{"version"?: "2.0" | null, "server": "valid" | {"invalid_at": ptr}, "client": ...}`.
Paths are JSON pointers. A missing required field points at the missing property. A node whose
`kind`-tagged action fails points inside the branch its `kind` selects; a non-object action points at
the action itself. The vitest side (`packages/ze-ui/src/fixtures.test.ts`) checks the `client` outcome.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ze_components import PRIMITIVE_TYPES
from ze_components.schema import export_json_schema

FIXTURES = Path(__file__).resolve().parents[4] / "packages" / "ze-ui" / "fixtures"
SCHEMA = export_json_schema()
DEFS = SCHEMA["$defs"]
MAPPING = SCHEMA["discriminator"]["mapping"]


def _pointer(parts) -> str:
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def _error_path(err) -> list:
    path = list(err.absolute_path)
    if err.validator == "required":
        missing = [p for p in err.validator_value if p not in err.instance]
        return path + [missing[0]]
    if err.validator == "oneOf" and isinstance(err.instance, dict):
        branches: dict[int, list] = {}
        for c in err.context:
            branches.setdefault(c.schema_path[0], []).append(c)
        matching = [
            errs
            for errs in branches.values()
            if not any(
                c.validator == "const" and list(c.absolute_path)[-1:] == ["kind"]
                for c in errs
            )
        ]
        if len(matching) == 1:
            return min(
                (_error_path(c) for c in matching[0]), key=lambda p: [str(x) for x in p]
            )
    return path


def first_error(node: object, path: list) -> str | None:
    if not isinstance(node, dict) or node.get("type") not in MAPPING:
        return _pointer(path + ["type"])
    name = MAPPING[node["type"]].rsplit("/", 1)[-1]
    schema = {
        "$schema": SCHEMA["$schema"],
        "$defs": {**DEFS, "Primitive": {}},
        "$ref": f"#/$defs/{name}",
    }
    errors = sorted(
        Draft202012Validator(schema).iter_errors(node),
        key=lambda e: [str(x) for x in _error_path(e)],
    )
    if errors:
        return _pointer(path + _error_path(errors[0]))
    # Not expressible in JSON Schema: one key per row.
    if (
        node["type"] == "table"
        and node.get("keys") is not None
        and len(node["keys"]) != len(node["rows"])
    ):
        return _pointer(path + ["keys"])
    for i, child in enumerate(node.get("children", [])):
        found = first_error(child, path + ["children", i])
        if found:
            return found
    return None


def first_tree_error(tree: list) -> str | None:
    for i, node in enumerate(tree):
        found = first_error(node, [i])
        if found:
            return found
    return None


def _fixture_names() -> list[str]:
    return sorted(
        p.name.removesuffix(".expect.json") for p in FIXTURES.glob("*.expect.json")
    )


@pytest.mark.parametrize("name", _fixture_names())
def test_fixture_matches_its_server_expectation(name: str):
    tree = json.loads((FIXTURES / f"{name}.json").read_text())
    expect = json.loads((FIXTURES / f"{name}.expect.json").read_text())["server"]
    found = first_tree_error(tree)
    if expect == "valid":
        assert found is None
    else:
        assert found == expect["invalid_at"]


def test_every_fixture_has_an_expectation_and_the_reverse():
    trees = {
        p.name.removesuffix(".json")
        for p in FIXTURES.glob("*.json")
        if not p.name.endswith(".expect.json")
    }
    assert trees == set(_fixture_names())


def _node_types(nodes: list) -> set[str]:
    found: set[str] = set()
    for node in nodes:
        if isinstance(node, dict):
            found.add(node.get("type"))
            found |= _node_types(node.get("children", []))
            found |= _node_types(
                [
                    a
                    for a in node.get("actions", [])
                    if isinstance(a, dict) and "type" in a
                ]
            )
    return found


@pytest.mark.parametrize("cls", PRIMITIVE_TYPES, ids=lambda c: c.__name__)
def test_every_primitive_type_has_a_server_valid_fixture(cls):
    tag = cls.__dataclass_fields__["type"].default
    valid: set[str] = set()
    for name in _fixture_names():
        if (
            json.loads((FIXTURES / f"{name}.expect.json").read_text())["server"]
            != "valid"
        ):
            continue
        valid |= _node_types(json.loads((FIXTURES / f"{name}.json").read_text()))
    assert tag in valid, tag
