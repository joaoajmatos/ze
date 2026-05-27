"""Test helpers for building a CapabilityGate from YAML-style config."""

from __future__ import annotations

from unittest.mock import MagicMock

from ze.capability.gate import CapabilityGate
from ze.capability.sync import sync_gate_registry
from ze_core.orchestration.registry import clear_registry as clear_zc_registry


def make_gate(
    agents_config: dict,
    *,
    override_store=None,
) -> CapabilityGate:
    from ze.agents import registry as ze_registry

    ze_registry._registry.clear()
    for name in agents_config:
        ze_registry._registry[name] = type("AgentStub", (), {"name": name})

    settings = MagicMock()
    settings.agent_configs = agents_config

    clear_zc_registry()
    sync_gate_registry(settings)
    return CapabilityGate(override_store=override_store)
