"""Tests for `ze_worldstate.bootstrap.loop_push_settings` (Phase 170 US5).

The loop push switch is read from config and passed to the arbitration job.
Defaults must match the pre-phase-170 behaviour: enabled, code thresholds,
12-hour inline cooldown.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ze_worldstate.bootstrap import LoopPushSettings, loop_push_settings


def _settings(config: Any) -> SimpleNamespace:
    return SimpleNamespace(config=config)


def test_defaults_when_config_is_empty():
    assert loop_push_settings(_settings({})) == LoopPushSettings(
        enabled=True, thresholds={}, inline_cooldown_hours=12.0
    )


def test_defaults_when_config_is_missing_or_not_a_dict():
    assert loop_push_settings(_settings(None)) == LoopPushSettings()
    assert loop_push_settings(_settings("not a dict")) == LoopPushSettings()


def test_defaults_when_push_block_is_absent_or_not_a_dict():
    assert loop_push_settings(_settings({"worldstate": {}})) == LoopPushSettings()
    assert loop_push_settings(_settings({"worldstate": {"push": None}})) == (
        LoopPushSettings()
    )


def test_reads_enabled_thresholds_and_cooldown():
    settings = _settings(
        {
            "worldstate": {
                "push": {
                    "enabled": False,
                    "thresholds": {"tau_confidence": 0.7},
                    "inline_cooldown_hours": 6.0,
                }
            }
        }
    )
    parsed = loop_push_settings(settings)
    assert parsed.enabled is False
    assert parsed.thresholds == {"tau_confidence": 0.7}
    assert parsed.inline_cooldown_hours == 6.0


def test_ignores_unknown_keys():
    settings = _settings(
        {
            "worldstate": {
                "push": {
                    "enabled": True,
                    "thresholds": {"tau_confidence": 0.5},
                    "inline_cooldown_hours": 5.0,
                    "not_a_real_key": "ignored",
                }
            }
        }
    )
    parsed = loop_push_settings(settings)
    assert parsed.enabled is True
    assert parsed.thresholds == {"tau_confidence": 0.5}
    assert parsed.inline_cooldown_hours == 5.0


def test_thresholds_is_never_shared_mutable_state():
    settings = _settings({"worldstate": {"push": {"thresholds": {}}}})
    first = loop_push_settings(settings)
    second = loop_push_settings(settings)
    assert first.thresholds is not second.thresholds
