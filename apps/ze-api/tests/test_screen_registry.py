from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from ze_core.screen import DuplicateScreenKindError
from ze_plugin.plugin import ZePlugin
from ze_sdk.screen import ResolveContext, ScreenLine, ScreenRef

from ze_api.wiring.screen import build_screen_registry

CORE_KINDS = {
    "goal",
    "goal_gate",
    "workflow",
    "workflow_execution",
    "held_write",
    "loop",
    "entity",
    "fact",
    "procedure",
    "skill",
    "workspace_run",
    "workspace_placed",
    "hypothesis",
    "notification",
}


class _Resolver:
    def __init__(self, *kinds):
        self.kinds = frozenset(kinds)

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        return []


def _registry(*plugins):
    stores = {
        k: AsyncMock()
        for k in (
            "goal_store",
            "workflow_store",
            "held_write_store",
            "loop_store",
            "memory_store",
            "graph_store",
            "procedure_store",
            "skill_store",
            "workspace_store",
            "hypothesis_store",
            "notification_store",
        )
    }
    return build_screen_registry(**stores, plugins=list(plugins))


def test_zeplugin_default_is_no_resolvers():
    assert ZePlugin.screen_resolvers(SimpleNamespace()) == []


def test_every_core_kind_is_registered_once():
    assert _registry().kinds == CORE_KINDS


def test_plugin_kinds_are_added():
    plugin = SimpleNamespace(
        screen_resolvers=lambda: [_Resolver("contact"), _Resolver("reminder")]
    )
    assert _registry(plugin).kinds == CORE_KINDS | {"contact", "reminder"}


def test_a_duplicate_kind_fails_startup():
    clash = SimpleNamespace(screen_resolvers=lambda: [_Resolver("goal")])
    with pytest.raises(DuplicateScreenKindError):
        _registry(clash)
