from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ze_agents.errors import AgentConfigError
from ze_plugin.ui import (
    ModuleResult,
    ModuleSubject,
    UiContribution,
    collect_ui_contributions,
    filter_ui_manifest_by_openapi,
    get_module,
    request_module_refresh,
)


async def _provider(subject: ModuleSubject) -> ModuleResult:
    return ModuleResult(applies=False, components=[])


def _module(
    *,
    id: str = "ze_news.sources",
    slot: str | None = "mind.entity",
    provider=_provider,
    priority: int = 100,
) -> UiContribution:
    return UiContribution(
        id=id,
        plugin="ze_news",
        kind="module",
        label="Sources",
        icon="newspaper",
        slot=slot,
        provider=provider,
        priority=priority,
    )


def _preset(
    *,
    id: str = "ze_news.whats_new",
    prompt: str | None = "What's new in my sources?",
    label: str = "What's new in my sources?",
    priority: int = 100,
) -> UiContribution:
    return UiContribution(
        id=id,
        plugin="ze_news",
        kind="preset",
        label=label,
        icon="newspaper",
        prompt=prompt,
        priority=priority,
    )


def _settings(
    *, id: str = "ze_news.settings", operation: str | None = "getNewsSettings"
) -> UiContribution:
    return UiContribution(
        id=id,
        plugin="ze_news",
        kind="settings_section",
        label="News",
        icon="newspaper",
        settings_operation_id=operation,
    )


def _plugin(*contributions: UiContribution):
    plugin = MagicMock()
    plugin.ui_contributions.return_value = list(contributions)
    return plugin


def test_empty_plugins_returns_empty_manifest():
    manifest = collect_ui_contributions([])
    assert manifest.modules == ()
    assert manifest.presets == ()
    assert manifest.settings_sections == ()


def test_collects_each_kind():
    manifest = collect_ui_contributions(
        [_plugin(_module(), _preset(), _settings())]
    )
    assert [m.id for m in manifest.modules] == ["ze_news.sources"]
    assert [p.id for p in manifest.presets] == ["ze_news.whats_new"]
    assert [s.id for s in manifest.settings_sections] == ["ze_news.settings"]


@pytest.mark.parametrize("kind", ["nav", "page", "foo"])
def test_unknown_or_removed_kind_raises_naming_the_id(kind):
    bad = UiContribution(
        id="ze_news.old", plugin="ze_news", kind=kind, label="Old", icon="x"
    )
    with pytest.raises(AgentConfigError, match="ze_news.old"):
        collect_ui_contributions([_plugin(bad)])


def test_module_without_slot_raises():
    with pytest.raises(AgentConfigError, match="ze_news.sources"):
        collect_ui_contributions([_plugin(_module(slot=None))])


def test_module_with_unknown_slot_raises():
    with pytest.raises(AgentConfigError, match="ze_news.sources"):
        collect_ui_contributions([_plugin(_module(slot="world.field"))])


def test_module_without_provider_raises():
    with pytest.raises(AgentConfigError, match="ze_news.sources"):
        collect_ui_contributions([_plugin(_module(provider=None))])


def test_preset_without_prompt_raises():
    with pytest.raises(AgentConfigError, match="ze_news.whats_new"):
        collect_ui_contributions([_plugin(_preset(prompt=None))])


def test_preset_prompt_over_300_characters_raises():
    with pytest.raises(AgentConfigError, match="ze_news.whats_new"):
        collect_ui_contributions([_plugin(_preset(prompt="x" * 301))])


def test_preset_label_over_40_characters_raises():
    with pytest.raises(AgentConfigError, match="ze_news.whats_new"):
        collect_ui_contributions([_plugin(_preset(label="x" * 41))])


def test_settings_section_without_operation_raises():
    with pytest.raises(AgentConfigError, match="ze_news.settings"):
        collect_ui_contributions([_plugin(_settings(operation=None))])


def test_duplicate_id_raises():
    with pytest.raises(AgentConfigError, match="Duplicate"):
        collect_ui_contributions([_plugin(_module(), _preset(id="ze_news.sources"))])


def test_lists_sort_by_priority_then_id():
    manifest = collect_ui_contributions(
        [
            _plugin(
                _module(id="b.mod", priority=50),
                _module(id="c.mod", priority=10),
                _module(id="a.mod", priority=50),
            )
        ]
    )
    assert [m.id for m in manifest.modules] == ["c.mod", "a.mod", "b.mod"]


def test_filter_drops_settings_section_with_missing_operation_keeps_the_rest():
    manifest = collect_ui_contributions(
        [_plugin(_module(), _preset(), _settings())]
    )
    filtered = filter_ui_manifest_by_openapi(manifest, frozenset())
    assert filtered.settings_sections == ()
    assert len(filtered.modules) == 1
    assert len(filtered.presets) == 1


def test_filter_keeps_settings_section_with_known_operation():
    manifest = collect_ui_contributions([_plugin(_settings())])
    filtered = filter_ui_manifest_by_openapi(manifest, frozenset({"getNewsSettings"}))
    assert len(filtered.settings_sections) == 1


def test_get_module_finds_by_id():
    manifest = collect_ui_contributions([_plugin(_module())])
    assert get_module(manifest, "ze_news.sources") is manifest.modules[0]
    assert get_module(manifest, "nope") is None


async def test_request_module_refresh_sends_module_screen():
    from unittest.mock import AsyncMock

    interface = MagicMock()
    interface.send_refresh = AsyncMock()
    await request_module_refresh(interface, "x.facet")
    interface.send_refresh.assert_awaited_once_with("module:x.facet")


async def test_request_module_refresh_logs_and_swallows_failure():
    from unittest.mock import AsyncMock

    interface = MagicMock()
    interface.send_refresh = AsyncMock(side_effect=RuntimeError("down"))
    await request_module_refresh(interface, "x.facet")
