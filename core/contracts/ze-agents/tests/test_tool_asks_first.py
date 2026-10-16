"""asks_first declaration on `@tool` (Phase 181)."""

from __future__ import annotations

import pytest

from ze_agents.errors import AgentConfigError
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import (
    AskDecision,
    ToolAccess,
    clear_tool_registry,
    get_tool,
    tool,
)


@pytest.fixture(autouse=True)
def clean():
    clear_tool_registry()
    yield
    clear_tool_registry()


def _fn(name: str, params: str = ""):
    ns: dict = {}
    exec(f"async def {name}({params}) -> str:\n    return 'ok'\n", ns)
    return ns[name]


def _irreversible(**kw):
    return dict(
        access=ToolAccess.WRITE,
        description="d",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="did a thing",
        **kw,
    )


def test_irreversible_defaults_to_asks_first() -> None:
    tool(**_irreversible())(_fn("w1"))
    spec = get_tool("w1")
    assert spec.asks_first is True
    assert spec.no_ask_reason is None


def test_opt_out_with_reason() -> None:
    tool(**_irreversible(asks_first=False, no_ask_reason="internal only"))(_fn("w2"))
    spec = get_tool("w2")
    assert spec.asks_first is False
    assert spec.no_ask_reason == "internal only"


def test_opt_out_without_reason_fails() -> None:
    with pytest.raises(AgentConfigError, match="no_ask_reason"):
        tool(**_irreversible(asks_first=False))(_fn("w3"))
    with pytest.raises(AgentConfigError, match="no_ask_reason"):
        tool(**_irreversible(asks_first=False, no_ask_reason="  "))(_fn("w3b"))


def test_reason_without_opt_out_fails() -> None:
    with pytest.raises(AgentConfigError, match="no_ask_reason"):
        tool(**_irreversible(no_ask_reason="because"))(_fn("w4"))


def test_explicit_true_fails() -> None:
    with pytest.raises(AgentConfigError, match="asks_first"):
        tool(**_irreversible(asks_first=True))(_fn("w5"))


def test_asks_first_on_reversible_fails() -> None:
    with pytest.raises(AgentConfigError, match="asks_first"):
        tool(
            access=ToolAccess.WRITE,
            description="d",
            reversibility=ToolReversibility.REVERSIBLE,
            undo_tool="u",
            undo_note="n",
            effect_phrase="x",
            asks_first=False,
            no_ask_reason="r",
        )(_fn("w6"))


def test_reversible_resolves_none() -> None:
    tool(
        access=ToolAccess.WRITE,
        description="d",
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="u",
        undo_note="n",
        effect_phrase="x",
    )(_fn("w7"))
    assert get_tool("w7").asks_first is None


def test_asks_first_on_read_fails() -> None:
    with pytest.raises(AgentConfigError):
        tool(access=ToolAccess.READ, description="d", asks_first=False)(_fn("r1"))
    with pytest.raises(AgentConfigError):
        tool(access=ToolAccess.READ, description="d", editable_field="x")(
            _fn("r2", "x: str")
        )


def test_editable_field_must_be_a_parameter() -> None:
    with pytest.raises(AgentConfigError, match="editable_field"):
        tool(**_irreversible(editable_field="body"))(_fn("w8", "to: str"))
    tool(**_irreversible(editable_field="body"))(_fn("w9", "to: str, body: str"))
    assert get_tool("w9").editable_field == "body"


def test_ask_check_and_summarize_stored() -> None:
    def check(args, ctx):
        return AskDecision.run()

    def summ(args):
        return "s"

    tool(**_irreversible(ask_check=check, summarize=summ))(_fn("w10"))
    spec = get_tool("w10")
    assert spec.ask_check is check
    assert spec.summarize is summ


def test_ask_check_allowed_on_reversible_write() -> None:
    tool(
        access=ToolAccess.WRITE,
        description="d",
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="u",
        undo_note="n",
        effect_phrase="x",
        ask_check=lambda a, c: AskDecision.run(),
    )(_fn("w11"))


def test_ask_decision_shapes() -> None:
    assert AskDecision.run().kind == "run"
    ask = AskDecision.ask("because")
    assert (ask.kind, ask.reason) == ("ask", "because")
    ref = AskDecision.refuse("no")
    assert (ref.kind, ref.message) == ("refuse", "no")
