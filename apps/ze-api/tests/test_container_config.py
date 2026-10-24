"""The app container's graph config carries everything the base container's does."""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

from ze_api.wiring.container import ZeContainer
from ze_core.container import Container
from ze_memory.extractor import gather_turn_proposals


def _container() -> ZeContainer:
    container = object.__new__(ZeContainer)
    for field in dataclasses.fields(ZeContainer):
        setattr(container, field.name, MagicMock())
    container.plugins = []
    return container


def test_build_config_carries_the_turn_extractor():
    configurable = _container()._build_config("t1")["configurable"]
    assert configurable["turn_extractor"] is gather_turn_proposals


def test_build_config_has_every_key_the_base_container_sets():
    container = _container()
    base_keys = set(Container._build_config(container, "t1")["configurable"])
    app_keys = set(container._build_config("t1")["configurable"])
    missing = sorted(base_keys - app_keys)
    assert not missing, f"ZeContainer._build_config is missing {missing}"
