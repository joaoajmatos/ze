from __future__ import annotations

from typing import TYPE_CHECKING

from ze_core.errors import AgentConfigError, UnknownAgentError

if TYPE_CHECKING:
    from ze_core.orchestration.base_agent import BaseAgent

_registry: dict[str, type[BaseAgent]] = {}


def agent(cls: type) -> type:
    """Register an agent class. Raises AgentConfigError on duplicate name."""
    name = getattr(cls, "name", None)
    if not name:
        raise AgentConfigError(f"{cls.__name__} must define a `name` class attribute")
    if name in _registry:
        raise AgentConfigError(f"Duplicate agent name {name!r}")
    _registry[name] = cls
    return cls


def get_agent_class(name: str) -> type[BaseAgent]:
    """Return the registered class for `name`. Raises UnknownAgentError if missing."""
    try:
        return _registry[name]
    except KeyError:
        raise UnknownAgentError(f"No agent registered with name {name!r}")


def get_registered_agents() -> dict[str, type[BaseAgent]]:
    """Return all registered classes, including disabled ones."""
    return dict(_registry)


def get_enabled_agents() -> dict[str, type[BaseAgent]]:
    """Return only agents with enabled = True."""
    return {name: cls for name, cls in _registry.items() if getattr(cls, "enabled", True)}


def clear_registry() -> None:
    """Clear all registered agents. Intended for use in tests only."""
    _registry.clear()
