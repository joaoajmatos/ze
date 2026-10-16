"""The base container hands the tier judge to every graph turn."""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock, patch

from ze_core import container
from ze_core.container import Container
from ze_core.routing.factory import build_tier_judge
from ze_core.routing.tier import ComplexitySurfaceConfig
from tests.support.routing import FakeSystemOneClient


def _container(**overrides) -> Container:
    values = {f.name: MagicMock() for f in dataclasses.fields(Container)}
    values["plugins"] = []
    values.update(overrides)
    return Container(**values)


def test_build_config_carries_the_tier_judge():
    judge = build_tier_judge(
        config={
            "system_one": {
                "enabled": True,
                "surfaces": {"complexity": {"enabled": True, "simple_max": 0.1}},
            }
        },
        system_one_client=FakeSystemOneClient(),
    )
    configurable = _container(tier_judge=judge)._build_config("t1")["configurable"]
    assert configurable["tier_judge"] is judge
    assert configurable["tier_judge"].surface == ComplexitySurfaceConfig(True, 0.1)


def test_from_config_builds_the_judge_beside_the_router():
    assert "build_tier_judge" in vars(container)
    with patch.object(container, "build_tier_judge") as factory:
        judge = container._build_tier_judge(
            settings=MagicMock(config={"system_one": {}}),
            system_one_client=FakeSystemOneClient(),
        )
    factory.assert_called_once()
    assert judge is factory.return_value
    assert factory.call_args.kwargs["config"] == {"system_one": {}}
