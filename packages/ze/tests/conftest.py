import pytest

import ze.tools  # noqa: F401 — registers all shared @tool decorators for every test


def _registry_has_real_agents() -> bool:
    from ze_core.orchestration.registry import get_registered_agents

    agents = get_registered_agents()
    if "research" not in agents:
        return False
    return not any(cls.__name__.startswith("GateConfig_") for cls in agents.values())


@pytest.fixture(autouse=True)
def _ensure_real_agent_registry():
    """Keep ze-core registry on real @agent classes, not capability test stubs."""
    from ze.agents.bootstrap import reload_agent_modules

    if not _registry_has_real_agents():
        reload_agent_modules()
    yield
    if not _registry_has_real_agents():
        reload_agent_modules()
