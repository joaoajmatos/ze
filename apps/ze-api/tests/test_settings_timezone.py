import pytest
from ze_api.settings import ZeApiSettings
from ze_core.orchestration.nodes.context import fetch_context


def _settings(tmp_path, *, yaml_tz: str | None = None) -> ZeApiSettings:
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    body = "models:\n  default: test\n"
    if yaml_tz is not None:
        body += f"timezone: {yaml_tz}\n"
    (config_dir / "config.yaml").write_text(body)
    return ZeApiSettings(_env_file=None, config_dir=config_dir)


def test_yaml_wins_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMEZONE", "America/New_York")
    s = _settings(tmp_path, yaml_tz="Europe/Lisbon")
    assert s.timezone == "Europe/Lisbon"
    assert s.to_core_settings().timezone == "Europe/Lisbon"


def test_env_when_yaml_has_no_key(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMEZONE", "America/New_York")
    s = _settings(tmp_path)
    assert s.timezone == "America/New_York"
    assert s.to_core_settings().timezone == "America/New_York"


def test_utc_when_neither_is_set(tmp_path, monkeypatch):
    monkeypatch.delenv("TIMEZONE", raising=False)
    s = _settings(tmp_path)
    assert s.timezone == "UTC"
    assert s.to_core_settings().timezone == "UTC"


def test_invalid_zone_falls_back_to_utc_with_one_warning(tmp_path, monkeypatch):
    from structlog.testing import capture_logs

    monkeypatch.setenv("TIMEZONE", "Not/AZone")
    s = _settings(tmp_path)
    with capture_logs() as logs:
        assert s.timezone == "UTC"
    warnings = [e for e in logs if e["event"] == "settings_timezone_invalid"]
    assert len(warnings) == 1
    assert s.to_core_settings().timezone == "UTC"


@pytest.mark.parametrize(
    ("yaml_tz", "expected"),
    [("Europe/Lisbon", "Europe/Lisbon"), (None, "UTC")],
)
async def test_fetch_context_builds_the_context_in_the_configured_zone(
    tmp_path, monkeypatch, yaml_tz, expected
):
    from unittest.mock import AsyncMock, MagicMock

    from ze_memory.types import MemoryContext

    monkeypatch.delenv("TIMEZONE", raising=False)
    store = AsyncMock()
    store.retrieve = AsyncMock(return_value=MemoryContext())
    store.get_session_summary = AsyncMock(return_value=None)
    embedder = MagicMock()
    embedder.encode_passage = embedder.encode_query = MagicMock(return_value=[0.1])
    config = {
        "configurable": {
            "memory_store": store,
            "embedder": embedder,
            "settings": _settings(tmp_path, yaml_tz=yaml_tz),
            "persona_store": None,
            "person_store": None,
            "turn_surfacer": None,
            "workflow_store": None,
        }
    }
    state = {
        "session_id": "s1",
        "prompt": "hi",
        "envelope": None,
        "messages": [],
        "last_active_at": None,
        "memory_context": None,
    }

    result = await fetch_context(state, config)

    assert result["agent_context"].timezone == expected
