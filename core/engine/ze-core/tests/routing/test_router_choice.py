"""Routing Choice after E5 — trust / decompose / abstain / skip on the router."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ze_agents.registry import clear_registry
from ze_agents.system_one import SystemOneResult
from ze_core.openrouter.system_one import DisabledSystemOneClient
from ze_core.routing.judge import RoutingSurfaceConfig
from ze_core.routing.router import EmbeddingRouter
from ze_core.routing.types import RouterConfig
from tests.support.routing import (
    FakeSystemOneClient,
    cosine_embedder,
    ok_result,
    register_agent,
)

CAL = RoutingSurfaceConfig(
    enabled=True,
    choice_trust=0.8,
    multi_specialist_hold=0.6,
    complexity_lookup_max=0.4,
    shortlist_k=3,
)
STATE = {"user": "what's on my calendar tomorrow", "history": "[Recent conversation]\nuser: hi"}


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def _router(scores, client=None, surface=CAL, agents=None) -> EmbeddingRouter:
    clear_registry()
    for name in agents or sorted(scores):
        register_agent(name, intents={"read": "Read"})
    return EmbeddingRouter(
        cosine_embedder(scores),
        AsyncMock(),
        routing_store=None,
        config=RouterConfig(),
        system_one_client=client,
        surface=surface,
    )


CLEAR = {"calendar": 0.84, "messenger": 0.50, "research": 0.45, "companion": 0.40}
CLOSE = {"calendar": 0.80, "messenger": 0.79, "research": 0.45, "companion": 0.40}
LOW = {"calendar": 0.60, "messenger": 0.40, "research": 0.35, "companion": 0.30}


async def _skip_envelope(scores):
    """The 160 result: no client, no surface."""
    router = _router(scores, client=None, surface=RoutingSurfaceConfig())
    return await router.route("hello", "s1")


class TestTrustClearSingle:
    @pytest.mark.parametrize(
        "text",
        ["what's on my calendar tomorrow", "o que tenho na agenda amanhã"],
    )
    async def test_clear_single_stays_single_with_peakedness_confidence(self, text):
        client = FakeSystemOneClient(ok_result(choice="calendar", peakedness=0.93))
        router = _router(CLEAR, client)
        env = await router.route(text, "s1", judgment_state={"user": text})
        assert env.is_compound is False
        assert env.routing_method == "embedding"
        assert env.primary_agent == "calendar"
        assert env.confidence == 0.93
        assert env.raw_scores == CLEAR
        assert env.score_gap == pytest.approx(0.84 - 0.50)

    async def test_one_call_with_bounded_shortlist_and_single_attempt(self):
        client = FakeSystemOneClient(ok_result(choice="calendar"))
        router = _router(CLEAR, client)
        await router.route("x", "s1", judgment_state=STATE)
        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["max_attempts"] == 1
        criteria = call["questions"]["agent"].criteria
        assert list(criteria) == ["calendar", "messenger", "research", "none"]
        assert call["state"]["user"] == STATE["user"]
        assert call["state"]["history"] == STATE["history"]
        assert set(call["questions"]) == {"agent", "multi_specialist", "complexity"}

    async def test_judgment_is_on_the_envelope(self):
        client = FakeSystemOneClient(ok_result(choice="calendar"))
        router = _router(CLEAR, client)
        env = await router.route("x", "s1", judgment_state=STATE)
        assert env.judgment is not None
        assert env.judgment.question_kinds == {
            "agent": "choice",
            "multi_specialist": "noul",
            "complexity": "score",
        }
        assert "agent" in env.judgment.consumed


class TestSkipIsTheOneSixtyPath:
    @pytest.mark.parametrize("scores", [CLEAR, CLOSE, LOW])
    async def test_disabled_client_equals_baseline(self, scores):
        baseline = await _skip_envelope(scores)
        router = _router(scores, DisabledSystemOneClient())
        env = await router.route("hello", "s1", judgment_state=STATE)
        assert _fields(env) == _fields(baseline)

    @pytest.mark.parametrize("scores", [CLEAR, CLOSE, LOW])
    async def test_null_bar_surface_off_and_no_state_equal_baseline(self, scores):
        baseline = await _skip_envelope(scores)
        client = FakeSystemOneClient(ok_result(choice="calendar"))
        null_bar = RoutingSurfaceConfig(enabled=True, choice_trust=0.8)
        for surface, state in (
            (null_bar, STATE),
            (RoutingSurfaceConfig(), STATE),
            (CAL, None),
        ):
            router = _router(scores, client, surface=surface)
            env = await router.route("hello", "s1", judgment_state=state)
            assert _fields(env) == _fields(baseline)
        assert client.calls == []

    async def test_single_enabled_agent_makes_no_call(self):
        client = FakeSystemOneClient(ok_result(choice="calendar"))
        router = _router({"calendar": 1.0}, client)
        env = await router.route("x", "s1", judgment_state=STATE)
        assert client.calls == []
        assert env.confidence == 1.0

    async def test_client_that_raises_is_a_skip(self):
        baseline = await _skip_envelope(CLEAR)
        client = FakeSystemOneClient(error=RuntimeError("boom"))
        router = _router(CLEAR, client)
        env = await router.route("hello", "s1", judgment_state=STATE)
        assert env.judgment is not None
        assert env.judgment.result.outcome == "skip"
        assert env.judgment.result.skip_reason == "error"
        assert env.judgment.consumed == frozenset()
        assert _fields(env) == _fields(baseline)

    async def test_client_skip_equals_baseline_and_keeps_reason(self):
        baseline = await _skip_envelope(CLOSE)
        client = FakeSystemOneClient(SystemOneResult(outcome="skip", skip_reason="timeout"))
        router = _router(CLOSE, client)
        env = await router.route("hello", "s1", judgment_state=STATE)
        assert _fields(env) == _fields(baseline)
        assert env.judgment.result.skip_reason == "timeout"


def _fields(env):
    return (
        env.primary_agent,
        env.confidence,
        env.score_gap,
        env.routing_method,
        env.is_compound,
        [(s.agent, s.intent, s.prompt, s.model) for s in env.subtasks],
        env.requires_synthesis,
        env.raw_scores,
        env.is_sequential,
        env.complexity,
        env.complexity_source,
    )
