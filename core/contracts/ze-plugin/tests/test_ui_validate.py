from __future__ import annotations

import pytest

from ze_agents.errors import InvalidComponentError
from ze_agents.registry import _registry
from ze_plugin.ui_validate import plugin_agent_tools, validate_plugin_tree


class _Agent:
    pass


class _FixtureAgent:
    __module__ = "fixture_plugin.agents.agent"
    tools = ["save_note", "list_notes"]


class _OtherAgent:
    __module__ = "other_plugin.agents.agent"
    tools = ["wipe"]


class _Plugin:
    def __init__(self, paths):
        self._paths = paths

    def agent_module_paths(self):
        return self._paths


@pytest.fixture(autouse=True)
def _agents():
    _registry["fixture"] = _FixtureAgent
    _registry["other"] = _OtherAgent
    yield
    _registry.pop("fixture", None)
    _registry.pop("other", None)


def _tool(owner="fixture", tool="save_note"):
    return {"kind": "tool", "owner": owner, "tool": tool, "args": {}}


def _button(action):
    return [{"type": "button", "label": "Go", "action": action}]


PLUGIN = _Plugin(["fixture_plugin.agents.agent"])


def test_agents_are_those_registered_under_the_plugin_module_paths():
    assert plugin_agent_tools(PLUGIN) == {
        "fixture": frozenset({"save_note", "list_notes"})
    }


def test_own_agent_tool_passes():
    validate_plugin_tree(PLUGIN, _button(_tool()))


def test_another_plugins_agent_fails():
    with pytest.raises(InvalidComponentError):
        validate_plugin_tree(PLUGIN, _button(_tool("other", "wipe")))


def test_tool_not_in_the_agents_list_fails():
    with pytest.raises(InvalidComponentError):
        validate_plugin_tree(PLUGIN, _button(_tool("fixture", "wipe")))


def test_plugin_without_agents_may_use_navigate_ask_compose():
    bare = _Plugin([])
    for action in (
        {"kind": "navigate", "route": "/ask"},
        {"kind": "ask", "text": "hi"},
        {"kind": "compose", "compose": "slipping"},
    ):
        validate_plugin_tree(bare, _button(action))
    with pytest.raises(InvalidComponentError):
        validate_plugin_tree(bare, _button(_tool()))


def test_nested_tool_action_is_found():
    tree = [{"type": "claim_list", "items": [{"text": "x", "action": _tool("other", "wipe")}]}]
    with pytest.raises(InvalidComponentError):
        validate_plugin_tree(PLUGIN, tree)


def _claim(**kw):
    return {"kind": "fact", "subject": "fact", "ref_id": "a", "source": "live_search", **kw}


def test_licensed_posture_passes():
    validate_plugin_tree(PLUGIN, [{"type": "headline", "text": "x", "claim": _claim()}])


@pytest.mark.parametrize(
    "bad",
    [
        {"kind": "priority"},
        {"kind": "action_record"},
        {"kind": "bogus"},
        {"subject": "loop"},
        {"source": "somewhere"},
    ],
)
def test_unlicensed_posture_fails(bad):
    with pytest.raises(InvalidComponentError):
        validate_plugin_tree(PLUGIN, [{"type": "headline", "text": "x", "claim": _claim(**bad)}])


def test_card_action_with_core_intent_fails():
    card = {
        "type": "claim_card",
        "title": "t",
        "claim": _claim(),
        "actions": [{"label": "ok", "intent": "approve_held_write", "ref_id": "1"}],
    }
    with pytest.raises(InvalidComponentError):
        validate_plugin_tree(PLUGIN, [card])
