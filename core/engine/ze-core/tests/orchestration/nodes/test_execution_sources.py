import pytest
from ze_agents.base_agent import BaseAgent
from ze_agents.registry import agent, clear_registry, register_instance
from ze_agents.types import AgentContext, AgentResult, Source
from ze_core.orchestration.nodes.execution import _run_with_timeout


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    yield
    clear_registry()


def _register(name: str, sources_on_result: list[Source]) -> None:
    async def run(self, ctx: AgentContext) -> AgentResult:
        ctx.sources.append(Source("https://ctx.test", "Ctx"))
        return AgentResult(agent=name, response="ok", sources=list(sources_on_result))

    cls = type(
        f"_A_{name}",
        (BaseAgent,),
        {"name": name, "description": "d", "tools": [], "run": run},
    )
    agent(cls)
    register_instance(name, cls())


async def test_context_sources_are_added_to_the_agent_result():
    _register("research", [])
    ctx = AgentContext(
        session_id="s",
        prompt="p",
    )

    result, _ = await _run_with_timeout("research", ctx)

    assert [s.url for s in result.sources] == ["https://ctx.test"]


async def test_result_sources_are_kept_without_duplicates():
    _register("research", [Source("https://ctx.test", "Ctx"), Source("https://b.test")])
    ctx = AgentContext(
        session_id="s",
        prompt="p",
    )

    result, _ = await _run_with_timeout("research", ctx)

    assert [s.url for s in result.sources] == ["https://ctx.test", "https://b.test"]
