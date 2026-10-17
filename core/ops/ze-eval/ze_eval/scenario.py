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


_COMPOSE_VALUES = ("slipping", "decisions", "topic")


def validate_context(context: object) -> dict:
    """A scenario `context:` is the inbound screen context: a dict with `screen`;
    `compose` must be one of the preset intents and `topic` needs a topic."""
    if not isinstance(context, dict) or not context.get("screen"):
        raise ValueError(f"context must be a mapping with a screen: {context!r}")
    compose = context.get("compose")
    if compose is not None and compose not in _COMPOSE_VALUES:
        raise ValueError(f"context.compose must be one of {_COMPOSE_VALUES}: {compose!r}")
    if compose == "topic" and not str(context.get("topic") or "").strip():
        raise ValueError("context.compose topic needs context.topic")
    return context


def turn_contexts(scenario: dict) -> list[dict | None]:
    """The context each turn sends. A turn's own `context` wins; the scenario's
    applies to the final prompt turn (the single prompt of a one-turn scenario)."""
    turns = scenario.get("turns") or [{"prompt": scenario.get("prompt")}]
    scenario_ctx = scenario.get("context")
    if scenario_ctx is not None:
        validate_context(scenario_ctx)
    last_prompt = max(
        (i for i, t in enumerate(turns) if "prompt" in t), default=None
    )
    contexts: list[dict | None] = []
    for i, turn in enumerate(turns):
        own = turn.get("context")
        if own is not None:
            contexts.append(validate_context(own))
        elif i == last_prompt:
            contexts.append(scenario_ctx)
        else:
            contexts.append(None)
    return contexts
