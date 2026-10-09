"""Reversibility declaration on `@tool` (Phase 165)."""

from __future__ import annotations

import pytest

from ze_agents.claims import ClaimKind
from ze_agents.errors import AgentConfigError
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import (
    ToolAccess,
    clear_tool_registry,
    get_tool,
    tool,
    validate_tool_declarations,
)


@pytest.fixture(autouse=True)
def clean():
    clear_tool_registry()
    yield
    clear_tool_registry()


def _fn(name: str):
    async def _impl() -> str:
        return "ok"

    _impl.__name__ = name
    return _impl


def test_feedback_record_claim_kind() -> None:
    assert ClaimKind.FEEDBACK_RECORD.value == "feedback_record"


def test_write_without_reversibility_fails_registration() -> None:
    with pytest.raises(AgentConfigError, match="must declare reversibility"):
        tool(access=ToolAccess.WRITE, description="d")(_fn("w"))


def test_read_with_any_declaration_fails() -> None:
    with pytest.raises(AgentConfigError):
        tool(
            access=ToolAccess.READ,
            description="d",
            reversibility=ToolReversibility.IRREVERSIBLE,
        )(_fn("r1"))
    with pytest.raises(AgentConfigError):
        tool(access=ToolAccess.READ, description="d", effect_phrase="x")(_fn("r2"))


def test_reversible_requires_undo_tool() -> None:
    with pytest.raises(AgentConfigError, match="undo_tool"):
        tool(
            access=ToolAccess.WRITE,
            description="d",
            reversibility=ToolReversibility.REVERSIBLE,
            undo_note="n",
        )(_fn("w"))


def test_reversible_requires_undo_note() -> None:
    with pytest.raises(AgentConfigError, match="undo_note"):
        tool(
            access=ToolAccess.WRITE,
            description="d",
            reversibility=ToolReversibility.REVERSIBLE,
            undo_tool="x",
        )(_fn("w"))


def test_irreversible_rejects_undo_tool() -> None:
    with pytest.raises(AgentConfigError):
        tool(
            access=ToolAccess.WRITE,
            description="d",
            reversibility=ToolReversibility.IRREVERSIBLE,
            undo_tool="x",
        )(_fn("w"))


def test_declaration_is_stored_on_spec() -> None:
    tool(
        access=ToolAccess.WRITE,
        description="d",
        reversibility="reversible",
        undo_tool="undo_it",
        undo_note="Does not recall notifications",
        effect_phrase="did a thing",
    )(_fn("do_it"))
    spec = get_tool("do_it")
    assert spec.reversibility is ToolReversibility.REVERSIBLE
    assert spec.undo_tool == "undo_it"
    assert spec.undo_note == "Does not recall notifications"
    assert spec.effect_phrase == "did a thing"


def test_read_tool_has_no_declaration() -> None:
    tool(access=ToolAccess.READ, description="d")(_fn("r"))
    assert get_tool("r").reversibility is None


def _write(name: str, **kw) -> None:
    tool(access=ToolAccess.WRITE, description="d", **kw)(_fn(name))


def test_validate_passes_when_undo_resolves() -> None:
    _write("undo_it", reversibility=ToolReversibility.IRREVERSIBLE)
    _write(
        "do_it",
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="undo_it",
        undo_note="n",
    )
    validate_tool_declarations()


def test_validate_fails_on_unregistered_undo() -> None:
    _write(
        "do_it",
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="missing",
        undo_note="n",
    )
    with pytest.raises(AgentConfigError, match="missing"):
        validate_tool_declarations()


def test_validate_fails_on_self_undo() -> None:
    _write(
        "do_it",
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="do_it",
        undo_note="n",
    )
    with pytest.raises(AgentConfigError, match="own undo_tool"):
        validate_tool_declarations()


def test_validate_fails_when_undo_is_read_tool() -> None:
    tool(access=ToolAccess.READ, description="d")(_fn("looker"))
    _write(
        "do_it",
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="looker",
        undo_note="n",
    )
    with pytest.raises(AgentConfigError, match="not a WRITE"):
        validate_tool_declarations()
