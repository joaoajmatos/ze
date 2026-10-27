"""Shipped config carries only live keys (Phase 170 US5, cleanup CF-08).

The executive-function audit found config keys that nothing read. This test
pins the cleaned shape: a deleted key cannot creep back, and an unread one
cannot come back silently.

`test_every_shipped_leaf_key_has_a_reader` scans the non-test Python source for
the key name as a quoted string, which is how every reader in the repo looks a
key up (`cfg.get("x")`, `cfg["x"]`). It catches a key nothing mentions. It
cannot tell two sections apart, so a generic name such as `enabled` passes on
any reader. A key read some other way (a dataclass built from `**cfg`) goes in
`READ_WITHOUT_LITERAL` with the reason.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

from ze_worldstate.bootstrap import LoopPushSettings, loop_push_settings

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config.yaml"

SOURCE_ROOTS = ("apps/ze-api", "core", "integrations", "packages", "plugins")
SKIPPED_DIRS = {"tests", "migrations", "node_modules", ".venv", "__pycache__"}
QUOTED_NAME = re.compile(r"""["']([A-Za-z_][A-Za-z0-9_]*)["']""")

READ_WITHOUT_LITERAL: dict[str, str] = {}


def _config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG_PATH.read_text())


def _leaf_keys(node: dict[str, Any], path: tuple[str, ...] = ()):
    for key, value in node.items():
        if isinstance(value, dict) and value:
            yield from _leaf_keys(value, (*path, key))
        else:
            yield (*path, key)


def _quoted_names_in_source() -> set[str]:
    names: set[str] = set()
    for root in SOURCE_ROOTS:
        for path in (REPO_ROOT / root).rglob("*.py"):
            if SKIPPED_DIRS & set(path.relative_to(REPO_ROOT).parts):
                continue
            names.update(QUOTED_NAME.findall(path.read_text(encoding="utf-8")))
    return names


def test_every_shipped_leaf_key_has_a_reader():
    quoted = _quoted_names_in_source()
    unread = [
        ".".join(path)
        for path in _leaf_keys(_config())
        if path[-1] not in quoted and ".".join(path) not in READ_WITHOUT_LITERAL
    ]
    assert unread == [], f"shipped config keys nothing reads: {unread}"


def test_worldstate_drift_has_no_window_days():
    drift = _config()["worldstate"]["drift"]
    assert set(drift) == {"enabled", "cron"}


def test_worldstate_push_keys_are_exact():
    push = _config()["worldstate"]["push"]
    assert set(push) == {
        "enabled",
        "inline_cooldown_hours",
        "repush_after_days",
        "thresholds",
    }
    assert push["repush_after_days"] == 7
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
