"""The conductor must finish before the web app declares delivery failed."""

import re
from pathlib import Path

from ze_agents.budget import DEFAULT_BUDGET_SECONDS

ROOT = Path(__file__).resolve().parents[3]


def _watchdog_seconds() -> float:
    src = (ROOT / "apps/ze-web/src/features/turn-stream/model/watchdog.ts").read_text()
    match = re.search(r"DELIVERY_WATCHDOG_MS\s*=\s*([\d_]+)", src)
    assert match
    return int(match.group(1).replace("_", "")) / 1000


def test_default_budget_is_below_the_delivery_watchdog():
    assert DEFAULT_BUDGET_SECONDS < _watchdog_seconds()


def test_shipped_config_budget_is_below_the_delivery_watchdog():
    import yaml

    config = yaml.safe_load((ROOT / "apps/ze-api/config/config.yaml").read_text())
    assert config["conductor"]["budget_seconds"] < _watchdog_seconds()
