"""choose_tier — the graph node that swaps in model_simple (phase 182)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ze_agents.registry import clear_registry
from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_agents.types import AgentContext
from ze_core.conversation.messages.types import JudgmentTrace, TierTrace
from ze_core.orchestration.judgment_state import build_tier_state
from ze_core.orchestration.nodes.tier import choose_tier
from ze_core.routing.tier import (
    Q_DEEP,
    ComplexitySurfaceConfig,
    TierJudge,
)
from ze_core.routing.types import RoutingEnvelope, SubTask
from ze_core.telemetry.context import (
    get_cost_context,
    set_agent_context,
    set_flow_context,
)
from tests.support.routing import FakeSystemOneClient, register_agent

ON = ComplexitySurfaceConfig(enabled=True, simple_max=0.2)


@pytest.fixture(autouse=True)
def registry():
    clear_registry()
    register_agent("t182", model="full-m", model_simple="light-m")
    yield
    clear_registry()


def _noul(value) -> SystemOneResult:
    return SystemOneResult(
        outcome="ok",
        model="jev",
        answers={Q_DEEP: SystemOneAnswer(type="noul", noul=value)},
        input_tokens=40,
        latency_ms=30,
    )


def _envelope(*agents: str, compound: bool = False) -> RoutingEnvelope:
    agents = agents or ("t182",)
    return RoutingEnvelope(
        primary_agent=agents[0],
        confidence=0.9,
        score_gap=0.3,
        routing_method="embedding",
        is_compound=compound,
        subtasks=[
            SubTask(agent=a, intent="read", prompt="thanks", model=f"{a}-full")
            for a in agents
        ],
        requires_synthesis=False,
    )


def _state(envelope=None, messages=None, **extra) -> dict:
    prompt = "thanks"
    ctx = AgentContext(
        session_id="s1",
        prompt=prompt,
        intent="read",
        messages=messages or [{"role": "user", "content": prompt}],
    )
    return {
        "session_id": "s1",
        "prompt": prompt,
        "image_caption": None,
        "agent_context": ctx,
        "memory_context": None,
        "routing_hints": None,
        "envelope": envelope if envelope is not None else _envelope(),
        "judgments": [JudgmentTrace(question_id="agent", kind="choice", latency_ms=1)],
        **extra,
    }


def _config(client=None, surface=ON, app_config=None, judge=None) -> dict:
    if judge is None and client is not None:
        judge = TierJudge(client, surface, app_config or {})
    return {"configurable": {"tier_judge": judge}}


class TestRequest:
    async def test_state_sent_is_build_tier_state(self):
        client = FakeSystemOneClient(_noul(0.9))
        state = _state()
        await choose_tier(state, _config(client))
        assert len(client.calls) == 1
        assert client.calls[0]["state"] == build_tier_state(state)
        assert list(client.calls[0]["questions"]) == [Q_DEEP]

    async def test_single_attempt(self):
        client = FakeSystemOneClient(_noul(0.9))
        await choose_tier(_state(), _config(client))
        assert client.calls[0]["max_attempts"] == 1

    async def test_judgment_rows_are_appended_after_existing_ones(self):
        client = FakeSystemOneClient(_noul(0.05))
        result = await choose_tier(_state(), _config(client))
        rows = result["judgments"]
        assert [r.question_id for r in rows] == ["agent", Q_DEEP]
        assert rows[1].kind == "noul" and rows[1].consumed

    async def test_cost_agent_context_is_router_during_the_call_then_restored(self):
        set_flow_context("chat", "s1")
        set_agent_context("companion")
        seen: list[str] = []

        class Recording(FakeSystemOneClient):
            async def evaluate(self, state, questions, *, max_attempts=None):
                seen.append(get_cost_context().agent)
                return await super().evaluate(
                    state, questions, max_attempts=max_attempts
                )

        await choose_tier(_state(), _config(Recording(_noul(0.9))))
        assert seen == ["router"]
        assert get_cost_context().agent == "companion"

    async def test_cost_agent_context_is_restored_when_the_client_raises(self):
        set_flow_context("chat", "s1")
        set_agent_context("companion")
        await choose_tier(
            _state(), _config(FakeSystemOneClient(error=RuntimeError("boom")))
        )
        assert get_cost_context().agent == "companion"

    @pytest.mark.parametrize(
        ("user", "assistant"),
        [
            ("plan my week around the Lisbon trip", "Mon: pack. Tue: flights."),
            ("planeia a minha semana à volta da viagem", "Seg: malas. Ter: voos."),
        ],
    )
    async def test_planning_exchange_sends_the_earlier_turns(self, user, assistant):
        client = FakeSystemOneClient(_noul(0.9))
        messages = [
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
            {"role": "user", "content": "ok go ahead with that plan"},
        ]
        state = _state(messages=messages, prompt="ok go ahead with that plan")
        await choose_tier(state, _config(client))
        sent = client.calls[0]["state"]
        assert user in sent["conversation"] and assistant in sent["conversation"]
        assert sent["task"] == "ok go ahead with that plan"


class TestDecision:
    @pytest.mark.parametrize(
        ("noul", "tier", "model"),
        [
            (0.1, "simple", "light-m"),
            (0.2, "simple", "light-m"),
            (0.21, "full", "t182-full"),
        ],
    )
    async def test_bar_maps_the_noul_to_a_model(self, noul, tier, model):
        result = await choose_tier(_state(), _config(FakeSystemOneClient(_noul(noul))))
        assert result["tier"] == TierTrace("t182", tier, "system_one", model)
        if tier == "simple":
            assert result["envelope"].subtasks[0].model == "light-m"
        else:
            assert "envelope" not in result

    async def test_the_input_envelope_is_not_mutated(self):
        state = _state()
        original = state["envelope"]
        await choose_tier(state, _config(FakeSystemOneClient(_noul(0.0))))
        assert original.subtasks[0].model == "t182-full"

    @pytest.mark.parametrize(
        ("client", "decided_by"),
        [
            (
                FakeSystemOneClient(
                    SystemOneResult(outcome="skip", skip_reason="timeout")
                ),
                "skip",
            ),
            (
                FakeSystemOneClient(
                    SystemOneResult(outcome="skip", skip_reason="error")
                ),
                "skip",
            ),
            (FakeSystemOneClient(error=RuntimeError("boom")), "skip"),
            (FakeSystemOneClient(_noul(1.5)), "invalid_answer"),
            (
                FakeSystemOneClient(SystemOneResult(outcome="ok", answers={})),
                "invalid_answer",
            ),
        ],
    )
    async def test_every_failure_keeps_the_full_model(self, client, decided_by):
        result = await choose_tier(_state(), _config(client))
        assert result["tier"] == TierTrace("t182", "full", decided_by, "t182-full")
        assert "envelope" not in result
        assert not result["judgments"][-1].consumed


class TestNoRequest:
    async def test_no_envelope_returns_nothing(self):
        client = FakeSystemOneClient(_noul(0.0))
        state = _state()
        state["envelope"] = None
        assert await choose_tier(state, _config(client)) == {}
        assert client.calls == []

    async def test_surface_off(self):
        client = FakeSystemOneClient(_noul(0.0))
        result = await choose_tier(
            _state(),
            _config(client, ComplexitySurfaceConfig(enabled=False, simple_max=0.2)),
        )
        assert result["tier"].decided_by == "off"
        assert result["tier"].tier == "full"
        assert client.calls == []
        assert "judgments" not in result

    async def test_no_judge_injected_is_off(self):
        result = await choose_tier(_state(), _config())
        assert result["tier"] == TierTrace("t182", "full", "off", "t182-full")

    async def test_null_bar_is_uncalibrated_and_warns_once_across_turns(self):
        client = FakeSystemOneClient(_noul(0.0))
        judge = TierJudge(client, ComplexitySurfaceConfig(enabled=True), {})
        with patch("ze_core.routing.tier.log") as log:
            first = await choose_tier(_state(), _config(judge=judge))
            second = await choose_tier(_state(), _config(judge=judge))
        assert first["tier"].decided_by == second["tier"].decided_by == "uncalibrated"
        assert client.calls == []
        assert log.warning.call_count == 1

    async def test_agent_without_model_simple(self):
        register_agent("plain", model="plain-m")
        client = FakeSystemOneClient(_noul(0.0))
        result = await choose_tier(_state(_envelope("plain")), _config(client))
        assert result["tier"] == TierTrace(
            "plain", "full", "no_simple_model", "plain-full"
        )
        assert client.calls == []

    async def test_override_that_equalises_the_tiers(self):
        client = FakeSystemOneClient(_noul(0.0))
        cfg = {"models": {"overrides": {"t182": "pinned"}}}
        result = await choose_tier(_state(), _config(client, app_config=cfg))
        assert result["tier"].decided_by == "no_simple_model"
        assert client.calls == []


class TestCompoundAndConductor:
    async def test_parallel_two_subtask_envelope(self):
        register_agent("other", model="other-m", model_simple="other-s")
        client = FakeSystemOneClient(_noul(0.0))
        env = _envelope("t182", "other")
        result = await choose_tier(_state(env), _config(client))
        assert result["tier"].decided_by == "compound"
        assert result["tier"].tier == "full"
        assert client.calls == []
        assert "envelope" not in result
        assert [s.model for s in env.subtasks] == ["t182-full", "other-full"]

    async def test_is_compound_envelope(self):
        client = FakeSystemOneClient(_noul(0.0))
        result = await choose_tier(_state(_envelope(compound=True)), _config(client))
        assert result["tier"].decided_by == "compound"
        assert client.calls == []

    async def test_conductor_rewritten_envelope(self):
        register_agent("companion", model="comp-m", model_simple="comp-s")
        client = FakeSystemOneClient(_noul(0.0))
        hint = [{"agent": "t182", "intent": "read", "prompt": "look it up"}]
        result = await choose_tier(
            _state(_envelope("companion"), conductor_hint=hint), _config(client)
        )
        assert result["tier"] == TierTrace(
            "companion", "full", "compound", "companion-full"
        )
        assert client.calls == []
