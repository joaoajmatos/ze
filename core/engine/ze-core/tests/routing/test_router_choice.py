"""Routing Choice after E5 — trust / decompose / abstain / skip on the router."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
STATE = {
    "user": "what's on my calendar tomorrow",
    "history": "[Recent conversation]\nuser: hi",
}


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
        client = FakeSystemOneClient(
            SystemOneResult(outcome="skip", skip_reason="timeout")
        )
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


class TestCloseScoresCanBeOneSpecialist:
    async def test_close_gap_with_confident_choice_is_not_compound(self):
        baseline = await _skip_envelope(CLOSE)
        assert baseline.is_compound is True  # what 160 alone would do
        client = FakeSystemOneClient(ok_result(choice="calendar", peakedness=0.9))
        router = _router(CLOSE, client)
        env = await router.route("x", "s1", judgment_state=STATE)
        assert env.is_compound is False
        assert env.primary_agent == "calendar"

    async def test_low_cosine_top_with_confident_choice_is_not_compound(self):
        baseline = await _skip_envelope(LOW)
        assert baseline.is_compound is True
        client = FakeSystemOneClient(ok_result(choice="calendar", peakedness=0.9))
        env = await _router(LOW, client).route("x", "s1", judgment_state=STATE)
        assert env.is_compound is False
        assert env.confidence == 0.9
        assert env.raw_scores == LOW

    @pytest.mark.parametrize("peakedness", [0.95, 0.2])
    async def test_choice_none_decomposes_even_when_cosine_is_clear(self, peakedness):
        client = FakeSystemOneClient(ok_result(choice="none", peakedness=peakedness))
        env = await _router(CLEAR, client).route("x", "s1", judgment_state=STATE)
        assert env.is_compound is True
        assert env.primary_agent == "calendar"  # E5 top
        assert env.confidence == peakedness
        assert env.routing_method == "embedding"

    async def test_unsure_choice_abstains_clear_top_stays_single(self):
        client = FakeSystemOneClient(ok_result(choice="messenger", peakedness=0.5))
        env = await _router(CLEAR, client).route("x", "s1", judgment_state=STATE)
        assert env.is_compound is False
        assert env.primary_agent == "calendar"
        assert env.confidence == CLEAR["calendar"]
        assert env.judgment.consumed == frozenset()

    async def test_unsure_choice_abstains_close_gap_stays_compound(self):
        client = FakeSystemOneClient(ok_result(choice="messenger", peakedness=0.5))
        env = await _router(CLOSE, client).route("x", "s1", judgment_state=STATE)
        assert env.is_compound is True
        assert env.confidence == CLOSE["calendar"]

    async def test_choice_may_disagree_with_e5_top(self):
        client = FakeSystemOneClient(ok_result(choice="messenger", peakedness=0.9))
        env = await _router(CLOSE, client).route("x", "s1", judgment_state=STATE)
        assert env.primary_agent == "messenger"
        assert env.is_compound is False
        assert env.subtasks[0].agent == "messenger"

    async def test_disagreement_is_logged(self):
        client = FakeSystemOneClient(ok_result(choice="messenger", peakedness=0.9))
        router = _router(CLOSE, client)
        with patch("ze_core.routing.router.log") as log:
            await router.route("x", "s1", judgment_state=STATE)
        events = [
            c
            for c in log.info.call_args_list
            if c.args[0] == "routing_choice_disagrees_e5"
        ]
        assert events
        assert events[0].kwargs["e5_top"] == "calendar"
        assert events[0].kwargs["choice"] == "messenger"


class TestMixedWorkAndComplexity:
    async def test_high_noul_decomposes_a_trusted_choice(self):
        client = FakeSystemOneClient(
            ok_result(choice="calendar", peakedness=0.9, noul=0.8)
        )
        env = await _router(CLEAR, client).route("x", "s1", judgment_state=STATE)
        assert env.is_compound is True
        assert env.primary_agent == "calendar"
        assert env.confidence == 0.9
        assert {"agent", "multi_specialist"} <= env.judgment.consumed

    async def test_low_noul_stays_single(self):
        client = FakeSystemOneClient(
            ok_result(choice="calendar", peakedness=0.9, noul=0.1)
        )
        env = await _router(CLEAR, client).route("x", "s1", judgment_state=STATE)
        assert env.is_compound is False

    async def test_score_sets_tier_and_source_without_changing_the_agent(self):
        simple = await _router(
            CLEAR, FakeSystemOneClient(ok_result(choice="calendar", score=0.2))
        ).route("x", "s1", judgment_state=STATE)
        complex_ = await _router(
            CLEAR, FakeSystemOneClient(ok_result(choice="calendar", score=0.9))
        ).route("x", "s1", judgment_state=STATE)
        assert (simple.complexity, simple.complexity_source) == ("simple", "score")
        assert (complex_.complexity, complex_.complexity_source) == ("complex", "score")
        assert simple.primary_agent == complex_.primary_agent == "calendar"
        assert "complexity" in simple.judgment.consumed

    async def test_score_missing_or_bar_null_uses_regex(self):
        no_score = await _router(
            CLEAR, FakeSystemOneClient(ok_result(choice="calendar"))
        ).route("hello", "s1", judgment_state=STATE)
        assert no_score.complexity_source == "regex"
        assert "complexity" not in no_score.judgment.consumed

        null_bar = RoutingSurfaceConfig(
            enabled=True, choice_trust=0.8, multi_specialist_hold=0.6
        )
        env = await _router(
            CLEAR,
            FakeSystemOneClient(ok_result(choice="calendar", score=0.1)),
            surface=null_bar,
        ).route("hello", "s1", judgment_state=STATE)
        assert env.complexity_source == "regex"

    async def test_score_also_applies_on_decompose_and_abstain_outcomes(self):
        none = await _router(
            CLEAR, FakeSystemOneClient(ok_result(choice="none", score=0.9))
        ).route("x", "s1", judgment_state=STATE)
        unsure = await _router(
            CLEAR,
            FakeSystemOneClient(
                ok_result(choice="calendar", peakedness=0.3, score=0.1)
            ),
        ).route("x", "s1", judgment_state=STATE)
        assert (none.complexity, none.complexity_source) == ("complex", "score")
        assert (unsure.complexity, unsure.complexity_source) == ("simple", "score")

    async def test_score_picks_the_subtask_model_tier(self):
        clear_registry()
        register_agent("calendar", model="big", model_simple="small")
        register_agent("messenger")
        router = EmbeddingRouter(
            cosine_embedder({"calendar": 0.84, "messenger": 0.5}),
            AsyncMock(),
            config=RouterConfig(),
            system_one_client=FakeSystemOneClient(
                ok_result(choice="calendar", score=0.1)
            ),
            surface=CAL,
        )
        env = await router.route("x", "s1", judgment_state=STATE)
        assert env.subtasks[0].model == "small"
