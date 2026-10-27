"""Tier judgment — surface config, model resolution, question, decision table, TierJudge."""

from __future__ import annotations

import math

import pytest

from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_core.routing.tier import (
    Q_DEEP,
    TIER_INSTRUCTIONS,
    ComplexitySurfaceConfig,
    TierDecision,
    TierJudge,
    build_tier_question,
    decide_tier,
    resolve_agent_model,
)
from ze_core.routing.types import RoutingEnvelope, SubTask
from tests.support.routing import FakeSystemOneClient, register_agent


def _settings(block) -> dict:
    return {"system_one": {"surfaces": {"complexity": block}}}


class _Settings:
    def __init__(self, config) -> None:
        self.config = config


def _cfg(block) -> ComplexitySurfaceConfig:
    return ComplexitySurfaceConfig.from_settings(_Settings(_settings(block)))


def _noul(value) -> SystemOneResult:
    return SystemOneResult(
        outcome="ok",
        model="jev",
        answers={Q_DEEP: SystemOneAnswer(type="noul", noul=value)},
        input_tokens=40,
        latency_ms=30,
    )


def _envelope(agent: str = "t182") -> RoutingEnvelope:
    return RoutingEnvelope(
        primary_agent=agent,
        confidence=0.9,
        score_gap=0.3,
        routing_method="embedding",
        is_compound=False,
        subtasks=[SubTask(agent=agent, prompt="hi", model="full-m")],
        requires_synthesis=False,
    )


class TestSurfaceConfig:
    def test_missing_block_is_off(self):
        assert ComplexitySurfaceConfig.from_settings({}) == ComplexitySurfaceConfig()
        assert ComplexitySurfaceConfig.from_settings(None) == ComplexitySurfaceConfig()
        assert (
            ComplexitySurfaceConfig.from_settings(_Settings({}))
            == ComplexitySurfaceConfig()
        )
        assert not ComplexitySurfaceConfig().calibrated

    def test_non_dict_block_is_off(self):
        assert _cfg("on") == ComplexitySurfaceConfig()

    def test_dict_and_settings_agree(self):
        block = {"enabled": True, "simple_max": 0.15}
        assert ComplexitySurfaceConfig.from_settings(
            _settings(block)
        ) == ComplexitySurfaceConfig.from_settings(_Settings(_settings(block)))

    def test_enabled_must_be_true(self):
        assert not _cfg({"enabled": "true", "simple_max": 0.2}).enabled
        assert not _cfg({"enabled": 1, "simple_max": 0.2}).enabled
        assert _cfg({"enabled": True, "simple_max": 0.2}).enabled

    @pytest.mark.parametrize("bar", [True, "0.2", -1, 1.5, math.nan])
    def test_invalid_bar_parses_to_none(self, bar):
        cfg = _cfg({"enabled": True, "simple_max": bar})
        assert cfg.simple_max is None
        assert cfg.enabled and not cfg.calibrated

    def test_enabled_with_bar_is_calibrated(self):
        assert _cfg({"enabled": True, "simple_max": 0.2}).calibrated

    def test_disabled_with_bar_is_not_calibrated(self):
        cfg = _cfg({"enabled": False, "simple_max": 0.2})
        assert cfg.simple_max == 0.2 and not cfg.calibrated


class TestResolveAgentModel:
    def test_full_and_simple_with_model_simple(self):
        register_agent("t182", model="full-m", model_simple="light-m")
        assert resolve_agent_model("t182", "full", {}) == "full-m"
        assert resolve_agent_model("t182", "simple", {}) == "light-m"

    def test_simple_without_model_simple_is_the_full_model(self):
        register_agent("t182", model="full-m")
        assert resolve_agent_model("t182", "simple", {}) == "full-m"

    def test_override_wins_for_both_tiers(self):
        register_agent("t182", model="full-m", model_simple="light-m")
        cfg = {"models": {"overrides": {"t182": "forced-m"}}}
        assert resolve_agent_model("t182", "full", cfg) == "forced-m"
        assert resolve_agent_model("t182", "simple", cfg) == "forced-m"

    def test_unknown_agent_uses_the_default(self):
        cfg = {"models": {"default": "dflt-m"}}
        assert resolve_agent_model("nope-182", "full", cfg) == "dflt-m"
        assert resolve_agent_model("nope-182", "simple", cfg) == "dflt-m"


class TestQuestion:
    def test_one_noul(self):
        questions = build_tier_question()
        assert list(questions) == [Q_DEEP] == ["needs_deep_reasoning"]
        assert questions[Q_DEEP].type == "noul"
        assert questions[Q_DEEP].instructions == TIER_INSTRUCTIONS

    def test_instructions_judge_the_task_not_only_the_last_message(self):
        text = TIER_INSTRUCTIONS.lower()
        assert "conversation" in text
        assert "history and context are background only" not in text


CFG = ComplexitySurfaceConfig(enabled=True, simple_max=0.2)


class TestDecideTier:
    def test_skip(self):
        result = SystemOneResult(outcome="skip", skip_reason="timeout")
        assert decide_tier(result, CFG) == TierDecision("full", "skip", False)

    def test_below_bar_is_simple(self):
        assert decide_tier(_noul(0.05), CFG) == TierDecision(
            "simple", "system_one", True
        )

    def test_equal_to_bar_is_simple(self):
        assert decide_tier(_noul(0.2), CFG) == TierDecision(
            "simple", "system_one", True
        )

    def test_above_bar_is_full(self):
        assert decide_tier(_noul(0.21), CFG) == TierDecision("full", "system_one", True)

    @pytest.mark.parametrize("value", [-0.01, 1.01, math.nan, None, "0.1", True])
    def test_bad_noul_value_is_invalid(self, value):
        result = SystemOneResult(
            outcome="ok",
            answers={Q_DEEP: SystemOneAnswer(type="noul", noul=value)},
        )
        assert decide_tier(result, CFG) == TierDecision("full", "invalid_answer", False)

    def test_missing_answer_is_invalid(self):
        result = SystemOneResult(outcome="ok", answers={})
        assert decide_tier(result, CFG) == TierDecision("full", "invalid_answer", False)

    def test_wrong_answer_type_is_invalid(self):
        result = SystemOneResult(
            outcome="ok", answers={Q_DEEP: SystemOneAnswer(type="score", score=0.1)}
        )
        assert decide_tier(result, CFG) == TierDecision("full", "invalid_answer", False)

    def test_bar_unset_never_downgrades(self):
        cfg = ComplexitySurfaceConfig(enabled=True, simple_max=None)
        assert decide_tier(_noul(0.0), cfg).tier == "full"


class TestTierJudge:
    async def test_asks_one_noul_with_one_attempt(self):
        register_agent("t182", model="full-m", model_simple="light-m")
        client = FakeSystemOneClient(_noul(0.05))
        judge = TierJudge(client, CFG, {})
        outcome = await judge.choose(_envelope(), {"task": "thanks"})
        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["state"] == {"task": "thanks"}
        assert list(call["questions"]) == [Q_DEEP]
        assert call["max_attempts"] == 1
        assert outcome.decision == TierDecision("simple", "system_one", True)
        assert outcome.model == "light-m"

    async def test_full_decision_keeps_the_full_model(self):
        register_agent("t182", model="full-m", model_simple="light-m")
        judge = TierJudge(FakeSystemOneClient(_noul(0.9)), CFG, {})
        outcome = await judge.choose(_envelope(), {"task": "plan my month"})
        assert outcome.decision.tier == "full"
        assert outcome.model == "full-m"

    async def test_judgment_row_matches_the_decision(self):
        register_agent("t182", model="full-m", model_simple="light-m")
        judge = TierJudge(FakeSystemOneClient(_noul(0.05)), CFG, {})
        outcome = await judge.choose(_envelope(), {"task": "thanks"})
        assert outcome.judgment is not None
        assert outcome.judgment.question_kinds == {Q_DEEP: "noul"}
        assert outcome.judgment.consumed == frozenset({Q_DEEP})
        assert outcome.judgment.skip_reason is None

    async def test_not_consumed_when_invalid(self):
        register_agent("t182", model="full-m", model_simple="light-m")
        judge = TierJudge(FakeSystemOneClient(_noul(1.5)), CFG, {})
        outcome = await judge.choose(_envelope(), {"task": "x"})
        assert outcome.decision == TierDecision("full", "invalid_answer", False)
        assert outcome.judgment is not None
        assert outcome.judgment.consumed == frozenset()
        assert outcome.judgment.skip_reason == "invalid_answer"

    async def test_raising_client_is_a_skip(self):
        register_agent("t182", model="full-m", model_simple="light-m")
        judge = TierJudge(FakeSystemOneClient(error=RuntimeError("boom")), CFG, {})
        outcome = await judge.choose(_envelope(), {"task": "x"})
        assert outcome.decision == TierDecision("full", "skip", False)
        assert outcome.model == "full-m"
        assert outcome.judgment is not None
        assert outcome.judgment.result.skip_reason == "error"
        assert outcome.judgment.consumed == frozenset()

    async def test_skip_result_keeps_the_client_reason(self):
        register_agent("t182", model="full-m", model_simple="light-m")
        client = FakeSystemOneClient(
            SystemOneResult(outcome="skip", skip_reason="timeout")
        )
        outcome = await TierJudge(client, CFG, {}).choose(_envelope(), {"task": "x"})
        assert outcome.decision == TierDecision("full", "skip", False)
        assert outcome.judgment is not None
        assert outcome.judgment.result.skip_reason == "timeout"

    def test_exposes_surface_for_the_node(self):
        judge = TierJudge(FakeSystemOneClient(_noul(0.0)), CFG, {})
        assert judge.surface is CFG
