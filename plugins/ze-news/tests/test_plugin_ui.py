from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import jsonschema
import pytest

from ze_components.schema import export_json_schema
from ze_news.plugin import NewsPlugin
from ze_news.types import Article
from ze_sdk.errors import InvalidComponentError
from ze_sdk.ui import ModuleSubject, validate_plugin_tree

CFG = {
    "news": {
        "enabled": True,
        "sources": [{"key": "bbc", "type": "rss", "url": "https://x"}],
    }
}
TOPIC = ModuleSubject(kind="entity", id="e1", label="climate", entity_type="topic")


def _plugin(config=CFG) -> NewsPlugin:
    settings = SimpleNamespace(config=config)
    return NewsPlugin(
        pool=MagicMock(),
        embedder=MagicMock(),
        settings=settings,
        openrouter_client=MagicMock(),
        nli_client=MagicMock(),
    )


def _article(n: int = 1) -> Article:
    return Article(
        url=f"https://example.com/{n}",
        source_key="bbc",
        title=f"Headline {n}",
        summary="s",
        published_at=datetime(2026, 10, n, tzinfo=timezone.utc),
        tags=["climate"],
    )


def _sources(plugin: NewsPlugin):
    return next(c for c in plugin.ui_contributions() if c.id == "ze_news.sources")


def test_contributions_when_enabled():
    by_id = {c.id: c for c in _plugin().ui_contributions()}

    preset = by_id["ze_news.whats_new"]
    assert preset.kind == "preset"
    assert preset.label == "What's new in my sources?"
    assert preset.prompt == "What's new in my sources?"
    module = by_id["ze_news.sources"]
    assert (module.kind, module.slot, module.label) == (
        "module",
        "mind.entity",
        "Sources",
    )
    assert by_id["ze_news.settings"].kind == "settings_section"


def test_no_contributions_when_disabled():
    assert _plugin({"news": {"enabled": False}}).ui_contributions() == []


async def test_provider_does_not_apply_before_startup():
    plugin = _plugin()
    plugin._store = None

    result = await _sources(plugin).provider(TOPIC)

    assert result.applies is False


async def test_provider_does_not_apply_to_other_entity_types():
    plugin = _plugin()
    plugin._store.by_tag = AsyncMock(return_value=[_article()])

    result = await _sources(plugin).provider(
        ModuleSubject(kind="entity", id="e2", label="Ana", entity_type="person")
    )

    assert result.applies is False
    plugin._store.by_tag.assert_not_called()


async def test_provider_does_not_apply_when_no_article_matches():
    plugin = _plugin()
    plugin._store.by_tag = AsyncMock(return_value=[])

    assert (await _sources(plugin).provider(TOPIC)).applies is False


async def test_provider_returns_a_licensed_claim_list_that_validates():
    plugin = _plugin()
    plugin._store.by_tag = AsyncMock(return_value=[_article(1), _article(2)])

    result = await _sources(plugin).provider(TOPIC)

    plugin._store.by_tag.assert_awaited_once_with("climate")
    assert result.applies is True
    (node,) = result.components
    assert node["type"] == "claim_list"
    assert len(node["items"]) == 2
    first = node["items"][0]
    assert (
        "Headline 1" in first["text"]
        and "bbc" in first["text"]
        and "2026" in first["text"]
    )
    assert first["claim"]["kind"] == "fact"
    assert first["claim"]["source"] == "live_search"
    validate_plugin_tree(plugin, result.components)
    schema = export_json_schema()
    jsonschema.validate(
        result.components,
        {"$defs": schema["$defs"], **schema["$defs"]["PrimitiveTree"]},
    )


def test_settings_tree_passes_the_shared_check_and_a_foreign_tool_action_raises():
    plugin = _plugin()
    from ze_news.ui.settings import build_news_settings

    validate_plugin_tree(plugin, build_news_settings(CFG["news"]))
    with pytest.raises(InvalidComponentError):
        validate_plugin_tree(
            plugin,
            [
                {
                    "type": "button",
                    "label": "x",
                    "action": {
                        "kind": "tool",
                        "owner": "other",
                        "tool": "t",
                        "args": {},
                    },
                }
            ],
        )
