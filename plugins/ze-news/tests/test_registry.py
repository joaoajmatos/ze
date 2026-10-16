from ze_news.registry import SourceRegistry, build_registry
from ze_news.types import SourceConfig


def _make_config(**kwargs) -> SourceConfig:
    defaults = dict(
        key="test", type="rss", url="https://example.com/rss", tags=["global"]
    )
    return SourceConfig(**{**defaults, **kwargs})


def test_build_registry_rss():
    registry = build_registry([_make_config(key="bbc", tags=["global", "general"])])
    assert registry.by_key("bbc") is not None


def test_build_registry_unknown_type():
    import pytest

    with pytest.raises(ValueError, match="Unknown news source type"):
        build_registry([_make_config(type="unknown")])


def test_by_key_missing():
    registry = SourceRegistry([])
    assert registry.by_key("nope") is None


def test_all():
    configs = [_make_config(key=f"src_{i}") for i in range(3)]
    registry = build_registry(configs)
    assert len(registry.all()) == 3
