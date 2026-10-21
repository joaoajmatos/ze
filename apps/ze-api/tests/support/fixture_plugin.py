"""A plugin that contributes one module per slot, a preset and a settings section.

Providers are plain functions a test can swap through `FixturePlugin.providers`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ze_agents.registry import _registry
from ze_plugin.plugin import ZePlugin
from ze_plugin.ui import ModuleResult, ModuleSubject, UiContribution

Provider = Callable[[ModuleSubject], Awaitable[ModuleResult]]

NOTE_TREE = [
    {
        "type": "claim_list",
        "title": "Notes",
        "items": [
            {
                "text": "A note",
                "claim": {
                    "kind": "fact",
                    "subject": "fact",
                    "ref_id": "n1",
                    "source": "live_search",
                },
            }
        ],
    }
]


class FixtureAgent:
    __module__ = "tests.support.fixture_plugin"
    name = "fixture"
    tools = ["save_note"]


def register_fixture_agent() -> None:
    _registry["fixture"] = FixtureAgent  # type: ignore[assignment]


def unregister_fixture_agent() -> None:
    _registry.pop("fixture", None)


async def applies(subject: ModuleSubject) -> ModuleResult:
    return ModuleResult(applies=True, components=[dict(n) for n in NOTE_TREE])


class FixturePlugin(ZePlugin):
    def __init__(self) -> None:
        self.providers: dict[str, Provider] = {
            "fixture_plugin.entity": applies,
            "fixture_plugin.run": applies,
            "fixture_plugin.card": applies,
        }

    def _via(self, module_id: str) -> Provider:
        async def call(subject: ModuleSubject) -> ModuleResult:
            return await self.providers[module_id](subject)

        return call

    def agent_module_paths(self) -> list[str]:
        return ["tests.support.fixture_plugin"]

    def ui_contributions(self) -> list[UiContribution]:
        def module(id: str, slot: str, label: str) -> UiContribution:
            return UiContribution(
                id=id,
                plugin="fixture_plugin",
                kind="module",
                label=label,
                icon="box",
                slot=slot,
                provider=self._via(id),
            )

        return [
            module("fixture_plugin.entity", "mind.entity", "Fixture facet"),
            module("fixture_plugin.run", "doing.run", "Fixture run"),
            module("fixture_plugin.card", "governance.connections", "Fixture card"),
            UiContribution(
                id="fixture_plugin.preset",
                plugin="fixture_plugin",
                kind="preset",
                label="Fixture preset",
                icon="box",
                prompt="Show the fixture",
            ),
            UiContribution(
                id="fixture_plugin.settings",
                plugin="fixture_plugin",
                kind="settings_section",
                label="Fixture",
                icon="box",
                settings_operation_id="getNewsSettings",
            ),
        ]
