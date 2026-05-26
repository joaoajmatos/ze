import pytest

from ze_core.capability.types import Mode
from ze_core.errors import AgentConfigError, UnknownAgentError
from ze_core.orchestration import (
    BaseAgent,
    agent,
    clear_registry,
    get_agent_class,
    get_enabled_agents,
    get_registered_agents,
)
from ze_core.orchestration.types import AgentContext, AgentResult


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def _make_agent(name: str, enabled: bool = True) -> type[BaseAgent]:
    _name = name

    class _Agent(BaseAgent):
        async def run(self, ctx: AgentContext) -> AgentResult:
            return AgentResult(agent=_name, response="ok")

    _Agent.name = _name
    _Agent.description = f"Agent {_name}"
    _Agent.enabled = enabled
    return _Agent


class TestAgentDecorator:
    def test_registers_class(self):
        cls = agent(_make_agent("alpha"))
        assert get_registered_agents()["alpha"] is cls

    def test_returns_class_unchanged(self):
        original = _make_agent("beta")
        returned = agent(original)
        assert returned is original

    def test_duplicate_name_raises(self):
        agent(_make_agent("gamma"))
        with pytest.raises(AgentConfigError, match="Duplicate agent name"):
            agent(_make_agent("gamma"))

    def test_missing_name_raises(self):
        class NoName(BaseAgent):
            async def run(self, ctx: AgentContext) -> AgentResult:
                return AgentResult(agent="", response="")

        with pytest.raises(AgentConfigError, match="must define a `name`"):
            agent(NoName)


class TestRegistryAccessors:
    def test_get_agent_class_returns_registered(self):
        cls = agent(_make_agent("delta"))
        assert get_agent_class("delta") is cls

    def test_get_agent_class_unknown_raises(self):
        with pytest.raises(UnknownAgentError, match="No agent registered"):
            get_agent_class("nonexistent")

    def test_get_registered_agents_includes_disabled(self):
        agent(_make_agent("enabled_one", enabled=True))
        agent(_make_agent("disabled_one", enabled=False))
        registered = get_registered_agents()
        assert "enabled_one" in registered
        assert "disabled_one" in registered

    def test_get_enabled_agents_excludes_disabled(self):
        agent(_make_agent("active", enabled=True))
        agent(_make_agent("inactive", enabled=False))
        enabled = get_enabled_agents()
        assert "active" in enabled
        assert "inactive" not in enabled

    def test_get_registered_agents_returns_copy(self):
        agent(_make_agent("epsilon"))
        snapshot = get_registered_agents()
        snapshot["injected"] = object()  # type: ignore[assignment]
        assert "injected" not in get_registered_agents()


class TestBaseAgentDefaults:
    def test_default_model(self):
        cls = _make_agent("zeta")
        assert cls.model == "anthropic/claude-sonnet-4-5"

    def test_default_enabled(self):
        cls = _make_agent("eta")
        assert cls.enabled is True

    def test_default_timeout(self):
        cls = _make_agent("theta")
        assert cls.timeout == 30

    async def test_stream_raises_not_implemented(self):
        cls = _make_agent("iota")
        instance = cls()  # type: ignore[call-arg]
        with pytest.raises(NotImplementedError):
            async for _ in instance.stream(None):  # type: ignore[arg-type]
                pass


class TestModeEnum:
    def test_mode_is_str_comparable(self):
        assert Mode.AUTONOMOUS == "autonomous"
        assert Mode.CONFIRM == "confirm"
        assert Mode.DRAFT_ONLY == "draft_only"
        assert Mode.DISABLED == "disabled"
