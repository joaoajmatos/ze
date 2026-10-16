"""Scenario loading from YAML files."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

# Set to 1 only when Ze's Google credentials point at a sandbox calendar.
# Scenarios with `requires_sandbox: true` create and delete events, so they
# are skipped unless this flag is set.
SANDBOX_ENV = "ZE_EVAL_SANDBOX"

# Default: eval/scenarios/ at the repo root (core/ops/ze-eval/ze_eval/ -> repo root)
_DEFAULT_SCENARIOS_DIR = (
    Path(__file__).parent.parent.parent.parent.parent / "eval" / "scenarios"
)


def load_scenarios(
    tag: str = "",
    scenarios_dir: Path | None = None,
) -> list[dict]:
    """Load all scenarios from YAML files, optionally filtered by tag."""
    base = scenarios_dir or _DEFAULT_SCENARIOS_DIR
    scenarios: list[dict] = []
    for path in sorted(base.glob("*.yaml")):
        items = yaml.safe_load(path.read_text()) or []
        for item in items:
            item.setdefault("file", path.stem)
            scenarios.append(item)
    if tag:
        scenarios = [s for s in scenarios if tag in s.get("tags", [])]
    return scenarios


def is_runnable(scenario: dict) -> bool:
    """False for a sandbox-only scenario when ZE_EVAL_SANDBOX=1 is not set."""
    if not scenario.get("requires_sandbox"):
        return True
    return os.environ.get(SANDBOX_ENV) == "1"


def load_scenario_by_id(
    scenario_id: str,
    scenarios_dir: Path | None = None,
) -> dict | None:
    """Return a single scenario by its id, or None if not found."""
    for scenario in load_scenarios(scenarios_dir=scenarios_dir):
        if scenario.get("id") == scenario_id:
            return scenario
    return None
