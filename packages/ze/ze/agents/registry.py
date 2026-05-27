"""Re-export ze-core agent registry (Phase 7 migration)."""

from ze_core.orchestration.registry import (
    _instances,
    _registry,
    agent,
    clear_registry,
    get_agent,
    get_agent_class,
    get_agent_instances,
    get_enabled_agents,
    get_registered_agents,
    register_instance,
)

# Backward-compatible alias for tests and transitional imports.
register = agent


def registered_names() -> list[str]:
    return list(_registry)


__all__ = [
    "agent",
    "register",
    "clear_registry",
    "get_agent",
    "get_agent_class",
    "get_agent_instances",
    "get_enabled_agents",
    "get_registered_agents",
    "register_instance",
    "registered_names",
    "_registry",
    "_instances",
]
