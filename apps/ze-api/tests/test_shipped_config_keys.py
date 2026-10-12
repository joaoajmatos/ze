"""Shipped config carries only live keys (Phase 170 US5).

The executive-function audit found config keys that nothing read. This test
pins the cleaned shape: a deleted key cannot creep back, and an unread one
cannot come back silently.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

from ze_worldstate.bootstrap import LoopPushSettings, loop_push_settings

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config.yaml"


def _config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG_PATH.read_text())


def test_worldstate_drift_has_no_window_days():
    drift = _config()["worldstate"]["drift"]
    assert set(drift) == {"enabled", "cron"}


def test_worldstate_push_keys_are_exact():
    push = _config()["worldstate"]["push"]
    assert set(push) == {"enabled", "inline_cooldown_hours", "thresholds"}
    assert set(push["thresholds"]) == {
        "tau_confidence",
        "tau_relevance",
        "novelty_similarity_max",
        "grounding_threshold",
    }
    assert push["thresholds"]["grounding_threshold"] == 0.3


def test_correlation_push_exposes_enabled_and_dry_run():
    push = _config()["correlation"]["push"]
    assert {"enabled", "dry_run"} <= set(push)


def test_correlation_salience_drops_unread_keys():
    salience = _config()["correlation"]["salience"]
    assert "feedback" not in salience
    assert "min_evidence" not in salience["surfacing"]


def test_loop_push_settings_matches_shipped_values():
    config = _config()
    parsed = loop_push_settings(SimpleNamespace(config=config))
    shipped = config["worldstate"]["push"]
    assert parsed == LoopPushSettings(
        enabled=shipped["enabled"],
        thresholds=shipped["thresholds"],
        inline_cooldown_hours=float(shipped["inline_cooldown_hours"]),
    )
