"""POST /eval/chat force_agent: honored only in eval mode, never in production."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_agents.base_agent import BaseAgent
from ze_agents.registry import agent, clear_registry
from ze_agents.types import AgentContext, AgentResult
from ze_api.api.routes.eval import router

KEY = "k"


def _register(name: str) -> None:
    class _A(BaseAgent):
        async def run(self, ctx: AgentContext) -> AgentResult:
            return AgentResult(agent=name, response="")

    _A.name = name
    _A.description = f"The {name} agent"
    _A.enabled = True
    agent(_A)


@pytest.fixture(autouse=True)
def registry():
    clear_registry()
    _register("research")
    yield
    clear_registry()


def _app(eval_mode: bool) -> tuple[FastAPI, AsyncMock]:
    invoke = AsyncMock(return_value=SimpleNamespace(error="stop-here"))
    app = FastAPI()
    app.state.settings = SimpleNamespace(ze_api_key=KEY, eval_mode=eval_mode)
    app.state.container = SimpleNamespace(invoke_raw_turn=invoke)
    app.include_router(router)
    return app, invoke


async def _post(app: FastAPI, body: dict):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post(
            "/eval/chat", json=body, headers={"Authorization": f"Bearer {KEY}"}
        )


async def test_forced_agent_reaches_the_graph_config_in_eval_mode():
    app, invoke = _app(eval_mode=True)
    resp = await _post(app, {"prompt": "hi", "force_agent": "research"})
    assert resp.status_code == 200
    assert invoke.await_args.kwargs["config_extra"] == {"forced_agent": "research"}


async def test_force_agent_is_refused_outside_eval_mode():
    app, invoke = _app(eval_mode=False)
    resp = await _post(app, {"prompt": "hi", "force_agent": "research"})
    assert resp.status_code == 403
    invoke.assert_not_awaited()


async def test_unknown_forced_agent_is_a_client_error():
    app, invoke = _app(eval_mode=True)
    resp = await _post(app, {"prompt": "hi", "force_agent": "nope"})
    assert resp.status_code == 400
    invoke.assert_not_awaited()


@pytest.mark.parametrize("eval_mode", [True, False])
async def test_plain_eval_chat_passes_no_config_extra(eval_mode):
    app, invoke = _app(eval_mode=eval_mode)
    resp = await _post(app, {"prompt": "hi"})
    assert resp.status_code == 200
    assert invoke.await_args.kwargs.get("config_extra") is None
