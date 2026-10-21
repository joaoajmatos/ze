"""ZeContainer puts the script runner into every turn config (Phase 197)."""

from __future__ import annotations

from tests.test_container_tier_judge import _container

from ze_api.wiring.container import ZeContainer


def test_build_config_carries_the_script_runner_key() -> None:
    configurable = _container(script_runner=None)._build_config("t1")["configurable"]
    assert "script_runner" in configurable
    assert configurable["script_runner"] is None


def test_build_config_passes_a_wired_runner_through() -> None:
    runner = object()
    configurable = _container(script_runner=runner)._build_config("t1")["configurable"]
    assert configurable["script_runner"] is runner


def test_container_defaults_to_no_script_runner() -> None:
    import dataclasses

    default = next(f for f in dataclasses.fields(ZeContainer) if f.name == "script_runner")
    assert default.default is None
