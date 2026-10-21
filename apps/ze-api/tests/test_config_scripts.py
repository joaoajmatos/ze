"""The shipped `workspace.scripts` block loads into ScriptLimits (Phase 197)."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from ze_agents.scripts import ScriptLimits

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config.yaml"


def test_shipped_scripts_block_gives_the_defaults(tmp_path: Path) -> None:
    copied = tmp_path / "config.yaml"
    shutil.copy(CONFIG_PATH, copied)
    config = yaml.safe_load(copied.read_text())

    assert set(config["workspace"]["scripts"]) == {
        "wall_seconds",
        "max_inner_calls",
        "max_proposed_writes",
        "max_spend_usd",
        "max_result_chars",
        "max_source_chars",
    }
    assert ScriptLimits.from_config(config) == ScriptLimits()
