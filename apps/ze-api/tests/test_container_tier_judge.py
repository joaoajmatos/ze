"""ZeContainer hands the tier judge to every graph turn; the shipped surface is off."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from unittest.mock import MagicMock

import yaml

from ze_api.container import ZeContainer
from ze_core.routing.factory import build_tier_judge
from ze_core.routing.tier import ComplexitySurfaceConfig

CONFIG = Path(__file__).resolve().parents[1] / "config" / "config.yaml"


def _container(**overrides) -> ZeContainer:
    container = object.__new__(ZeContainer)
    for field in dataclasses.fields(ZeContainer):
        setattr(container, field.name, MagicMock())
    container.plugins = []
    for name, value in overrides.items():
        setattr(container, name, value)
    return container


def test_build_config_carries_the_tier_judge_from_the_yaml_surface():
    config = yaml.safe_load(CONFIG.read_text())
    judge = build_tier_judge(config=config, system_one_client=MagicMock())
    configurable = _container(tier_judge=judge)._build_config("t1")["configurable"]
    assert configurable["tier_judge"] is judge
    assert judge.surface == ComplexitySurfaceConfig(enabled=False, simple_max=None)
