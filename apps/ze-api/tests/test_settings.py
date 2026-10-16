import pytest
from ze_api.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def make_settings(**overrides) -> Settings:
    defaults = dict(
        openrouter_api_key="test-key",
        database_url="postgresql://ze:ze@localhost:5432/ze",
        database_url_sync="postgresql+psycopg2://ze:ze@localhost:5432/ze",
        ze_api_key="test-api-key",
    )
    return Settings(**{**defaults, **overrides})


def test_config_loads_yaml():
    s = make_settings()
    config = s.config
    assert "models" in config
    assert "default" in config["models"]


def test_routing_yaml_mirrors_e5_defaults():
    from ze_agents.defaults import ROUTING_GAP_THRESHOLD, ROUTING_THRESHOLD

    s = make_settings()
    assert s.routing_config["threshold"] == ROUTING_THRESHOLD
    assert s.routing_config["gap_threshold"] == ROUTING_GAP_THRESHOLD


def test_settings_without_routing_yaml_overlay_is_empty(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("models:\n  default: test\n")
    s = make_settings(config_dir=config_dir)
    assert s.routing_config == {}
    from ze_agents.defaults import ROUTING_GAP_THRESHOLD, ROUTING_THRESHOLD
    from ze_core.routing.types import RouterConfig

    cfg = RouterConfig()
    assert cfg.threshold == ROUTING_THRESHOLD == 0.73
    assert cfg.gap_threshold == ROUTING_GAP_THRESHOLD == 0.02


def test_config_has_no_agents_block():
    s = make_settings()
    assert s.config.get("agents", {}) == {}


def test_get_settings_is_cached():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_default_confirm_timeout():
    s = make_settings()
    assert s.confirm_timeout_seconds == 900


def test_auto_migrate_defaults_off():
    s = make_settings()
    assert s.auto_migrate is False


def test_auto_migrate_reads_env(monkeypatch):
    monkeypatch.setenv("AUTO_MIGRATE", "true")
    s = make_settings()
    assert s.auto_migrate is True


# ── Config profiles (cost audit 2026-10) ──────────────────────────────────────


def _config_dir(tmp_path, base: str, profiles: dict[str, str] | None = None):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(base)
    if profiles:
        (config_dir / "profiles").mkdir()
        for name, body in profiles.items():
            (config_dir / "profiles" / f"{name}.yaml").write_text(body)
    return config_dir


def test_no_profile_leaves_config_untouched(tmp_path):
    config_dir = _config_dir(tmp_path, "news:\n  enabled: true\n")
    assert make_settings(config_dir=config_dir, ze_profile="").config == {
        "news": {"enabled": True}
    }


def test_profile_deep_merges_over_base(tmp_path):
    config_dir = _config_dir(
        tmp_path,
        "news:\n  enabled: true\n  credibility:\n    llm_scoring: true\n    model: m\n"
        "dream:\n  enabled: true\n  cron: '0 3 * * *'\n",
        {
            "quiet": "news:\n  credibility:\n    llm_scoring: false\ndream:\n  enabled: false\n"
        },
    )
    config = make_settings(config_dir=config_dir, ze_profile="quiet").config
    assert config["news"]["enabled"] is True
    assert config["news"]["credibility"] == {"llm_scoring": False, "model": "m"}
    assert config["dream"] == {"enabled": False, "cron": "0 3 * * *"}


def test_profile_replaces_lists_and_scalars(tmp_path):
    config_dir = _config_dir(
        tmp_path,
        "a:\n  items: [1, 2, 3]\n  n: 1\n",
        {"quiet": "a:\n  items: [9]\n  n: 2\n"},
    )
    config = make_settings(config_dir=config_dir, ze_profile="quiet").config
    assert config["a"] == {"items": [9], "n": 2}


def test_unknown_profile_is_a_typed_error(tmp_path):
    from ze_api.errors import ProfileConfigError

    config_dir = _config_dir(tmp_path, "a: 1\n")
    with pytest.raises(ProfileConfigError):
        make_settings(config_dir=config_dir, ze_profile="nope").config


def test_profile_name_cannot_escape_the_profiles_dir(tmp_path):
    from ze_api.errors import ProfileConfigError

    config_dir = _config_dir(tmp_path, "a: 1\n")
    with pytest.raises(ProfileConfigError):
        make_settings(config_dir=config_dir, ze_profile="../config").config


def test_profile_reads_env(monkeypatch):
    monkeypatch.setenv("ZE_PROFILE", "quiet")
    assert make_settings().ze_profile == "quiet"


def test_shipped_quiet_profile_only_overrides_shipped_keys():
    """A typo in the overlay would silently do nothing, so every key must exist in config.yaml."""
    base = make_settings(ze_profile="").config
    quiet = make_settings(ze_profile="quiet")

    # Read with a code default and only documented in comments in config.yaml.
    code_default_keys = {
        "memory.consolidation.enabled",
        "memory.session_summary",
    }

    def _walk(overlay, node, path=()):
        for key, value in overlay.items():
            dotted = ".".join((*path, key))
            if dotted in code_default_keys:
                continue
            assert key in node, f"quiet profile key {dotted} is not in config.yaml"
            if isinstance(value, dict):
                _walk(value, node[key], (*path, key))

    import yaml

    overlay = yaml.safe_load((quiet.config_dir / "profiles" / "quiet.yaml").read_text())
    _walk(overlay, base)


def test_shipped_quiet_profile_turns_the_llm_noise_off():
    config = make_settings(ze_profile="quiet").config
    assert config["news"]["credibility"]["llm_scoring"] is False
    assert config["proactive"]["catch_up"] is False
    assert config["dream"]["enabled"] is False
    assert config["proactive"]["insights"]["enabled"] is False
    assert config["correlation"]["push"]["dry_run"] is False
    # evals and manual testing need the per-turn System One surfaces untouched
    full = make_settings(ze_profile="").config
    assert config["system_one"] == full["system_one"]
