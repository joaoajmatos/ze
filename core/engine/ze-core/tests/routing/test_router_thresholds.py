"""Every envelope carries the router's bars so the trace can draw them (187b)."""

import json
from unittest.mock import AsyncMock

import pytest

from ze_agents.registry import clear_registry
from ze_core.orchestration.nodes.context import _companion_envelope
from ze_core.orchestration.nodes.routing import apply_conductor_rewrite, decompose
from ze_core.routing.router import EmbeddingRouter
from ze_core.routing.types import RouterConfig, RoutingEnvelope, SubTask

from tests.routing.test_router import (
    _FakeEmbedder,
    _make_client,
    _make_routing_store,
    _register,
)

CFG = RouterConfig(threshold=0.61, gap_threshold=0.07)


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def _router(*names: str, vecs: dict | None = None) -> EmbeddingRouter:
    for name in names:
        _register(name)
    vecs = vecs or {n: [1.0 - 0.1 * i, 0.0] for i, n in enumerate(sorted(names))}
    return EmbeddingRouter(
        _FakeEmbedder(vecs, [1.0, 0.0]),
        _make_client(),
        _make_routing_store(),
        config=CFG,
    )


def _bars(env: RoutingEnvelope) -> tuple[float, float]:
    return env.threshold, env.gap_threshold


class TestRouterEnvelopes:
    async def test_embedding_envelope(self):
        env = await _router("alpha", "beta").route("hello", "s1")
        assert _bars(env) == (0.61, 0.07)
        assert env.raw_scores

    async def test_single_agent_envelope(self):
        env = await _router("solo").route("hello", "s1")
        assert _bars(env) == (0.61, 0.07)

    @pytest.mark.parametrize("method", ["forced", "screen"])
    async def test_forced_and_screen_envelopes(self, method):
        router = _router("alpha", "beta")
        env = await router.route_forced("hello", "s1", "beta", method=method)
        assert env.routing_method == method
        assert _bars(env) == (0.61, 0.07)

    def test_exposes_config(self):
        assert _router("alpha", "beta").config is CFG


class TestNodeEnvelopes:
    async def test_decompose_node_stamps_bars_on_haiku_envelope(self):
        router = _router("alpha", "beta")
        client = AsyncMock()
        client.complete = AsyncMock(
            return_value=json.dumps(
                {"subtasks": [{"agent": "alpha", "prompt": "x", "changes": False}]}
            )
        )
        env = RoutingEnvelope(
            primary_agent="alpha",
            confidence=0.4,
            score_gap=0.1,
            routing_method="embedding",
            is_compound=True,
            subtasks=[SubTask(agent="alpha", prompt="x")],
            requires_synthesis=False,
            raw_scores={"alpha": 0.4, "beta": 0.3},
        )
        out = await decompose(
            {"session_id": "s1", "prompt": "x", "envelope": env},
            {"configurable": {"openrouter_client": client, "router": router}},
        )
        assert out["envelope"].routing_method == "haiku"
        assert _bars(out["envelope"]) == (0.61, 0.07)

    def test_conductor_rewrite_keeps_bars(self):
        env = RoutingEnvelope(
            primary_agent="alpha",
            confidence=0.4,
            score_gap=0.1,
            routing_method="haiku",
            is_compound=True,
            subtasks=[
                SubTask(agent="alpha", prompt="a"),
                SubTask(agent="beta", prompt="b"),
            ],
            requires_synthesis=False,
            is_sequential=True,
            threshold=0.61,
            gap_threshold=0.07,
        )
        rewritten, hint = apply_conductor_rewrite(env, "a then b")
        assert hint is not None
        assert _bars(rewritten) == (0.61, 0.07)

    @pytest.mark.parametrize("method", ["preset", "open_query"])
    def test_companion_reroute_carries_bars(self, method):
        router = _router("goals", "companion")
        env = RoutingEnvelope(
            primary_agent="goals",
            confidence=0.9,
            score_gap=0.3,
            routing_method="embedding",
            is_compound=False,
            subtasks=[SubTask(agent="goals", prompt="p")],
            requires_synthesis=False,
            threshold=0.61,
            gap_threshold=0.07,
        )
        out = _companion_envelope(env, {"configurable": {"router": router}}, method)
        assert out is not None
        assert out.routing_method == method
        assert _bars(out) == (0.61, 0.07)
