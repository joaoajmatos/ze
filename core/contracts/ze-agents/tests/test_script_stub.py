"""Pure helpers for the ze_tools stub that a script imports."""

from __future__ import annotations

from ze_agents.script_stub import (
    build_stub,
    normalize_source,
    source_hash,
    tool_signature,
)

READ_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_transactions",
        "description": "List transactions.",
        "parameters": {
            "type": "object",
            "properties": {
                "period": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["period"],
        },
    },
}

POSITIONS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_positions",
        "description": "List open positions.",
        "parameters": {"type": "object", "properties": {}},
    },
}


def test_build_stub_renders_typed_keyword_only_function() -> None:
    stub = build_stub([READ_SCHEMA])

    assert "def get_transactions(*, period: str, limit: int = None):" in stub
    assert '"""List transactions."""' in stub
    assert (
        'return _call("get_transactions", '
        '{k: v for k, v in {"period": period, "limit": limit}.items() if v is not None})'
    ) in stub


def test_build_stub_maps_json_types_and_leaves_others_unannotated() -> None:
    schema = {
        "type": "function",
        "function": {
            "name": "probe",
            "description": "Probe types.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "string"},
                    "b": {"type": "integer"},
                    "c": {"type": "number"},
                    "d": {"type": "boolean"},
                    "e": {"type": "array"},
                    "f": {"type": "object"},
                    "g": {"type": ["string", "null"]},
                    "h": {},
                },
                "required": ["a", "b", "c", "d", "e", "f", "g", "h"],
            },
        },
    }

    stub = build_stub([schema])

    assert (
        "def probe(*, a: str, b: int, c: float, d: bool, e: list, f: dict, g, h):"
    ) in stub


def test_build_stub_skips_names_that_are_not_identifiers() -> None:
    bad_tool = {
        "type": "function",
        "function": {
            "name": "bad-name",
            "description": "Not a Python name.",
            "parameters": {"type": "object", "properties": {}},
        },
    }
    bad_property = {
        "type": "function",
        "function": {
            "name": "get_positions",
            "description": "List open positions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bad-name": {"type": "string"},
                    "ok": {"type": "string"},
                },
            },
        },
    }

    stub = build_stub([bad_tool, bad_property])

    assert "bad-name" not in stub.replace('"bad-name"', "")
    assert "def get_positions(*, ok: str = None):" in stub


def test_build_stub_output_does_not_depend_on_input_order() -> None:
    forward = build_stub([READ_SCHEMA, POSITIONS_SCHEMA])
    reverse = build_stub([POSITIONS_SCHEMA, READ_SCHEMA])

    assert forward == reverse


def test_build_stub_always_defines_propose_and_finish() -> None:
    stub = build_stub([])

    assert "def propose(tool: str, **args) -> dict:" in stub
    assert "def finish(result, writes=None):" in stub


def test_build_stub_imports_call_and_error_from_base() -> None:
    stub = build_stub([READ_SCHEMA])

    assert "from ze_tools_base import ToolError, _call, _finish" in stub


def test_build_stub_compiles() -> None:
    stub = build_stub([READ_SCHEMA, POSITIONS_SCHEMA])

    compile(stub, "ze_tools.py", "exec")


def test_normalize_source_strips_comments_and_blank_lines() -> None:
    assert normalize_source("x = 1  # c\n\n\ny = 'a # b'\n") == "x = 1\ny = 'a # b'"


def test_source_hash_ignores_comments_and_blank_lines() -> None:
    plain = "x = 1\ny = 2\n"
    decorated = "# header\nx = 1  # one\n\n\ny = 2\n"

    assert source_hash(plain) == source_hash(decorated)


def test_source_hash_changes_with_literals() -> None:
    assert source_hash("x = 'a'\n") != source_hash("x = 'b'\n")


def test_tool_signature_collapses_repeated_names_keeping_first_order() -> None:
    assert tool_signature(
        "finance", ["get_transactions", "get_positions", "get_transactions"]
    ) == tool_signature("finance", ["get_transactions", "get_positions"])


def test_tool_signature_depends_on_order_and_agent() -> None:
    base = tool_signature("finance", ["get_transactions", "get_positions"])

    assert base != tool_signature("finance", ["get_positions", "get_transactions"])
    assert base != tool_signature("calendar", ["get_transactions", "get_positions"])
