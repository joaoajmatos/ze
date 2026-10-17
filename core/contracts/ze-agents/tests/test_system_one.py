"""Tests for SystemOneClient protocol and request/result dataclasses."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ze_agents.client import LLMClient
from ze_agents.system_one import (
    SystemOneAnswer,
    SystemOneClient,
    SystemOneQuestion,
    SystemOneResult,
    parse_bar,
    surface_block,
    valid_choice,
    valid_noul,
)


def test_noul_question_wire_type():
    q = SystemOneQuestion(type="noul", instructions="Is this a bug?")
    assert q.type == "noul"
    assert q.to_wire() == {"type": "noul", "instructions": "Is this a bug?"}


def test_choice_and_score_questions():
    choice = SystemOneQuestion(
        type="choice",
        instructions="Which agent?",
        criteria={"calendar": "events", "companion": "chat"},
    )
    score = SystemOneQuestion(
        type="score",
        instructions="How urgent?",
        criteria=["Can wait", "This week", "Blocking"],
    )
    assert choice.to_wire()["criteria"]["calendar"] == "events"
    assert score.to_wire()["criteria"][2] == "Blocking"


def test_ok_result_exposes_noul_without_json_parsing():
    result = SystemOneResult(
        outcome="ok",
        answers={"refund": SystemOneAnswer(type="noul", noul=0.9)},
    )
    assert result.answers["refund"].noul == 0.9
    assert result.skip_reason is None


def test_skip_result_is_distinct_from_ok():
    result = SystemOneResult(outcome="skip", skip_reason="timeout")
    assert result.outcome == "skip"
    assert result.answers == {}
    assert result.skip_reason == "timeout"


def test_protocol_is_not_llm_client():
    assert hasattr(SystemOneClient, "evaluate")
    assert not hasattr(LLMClient, "evaluate")


class _FakeSystemOne:
    async def evaluate(self, state, questions, *, max_attempts=None):
        return SystemOneResult(outcome="ok")


def test_runtime_checkable_protocol():
    assert isinstance(_FakeSystemOne(), SystemOneClient)


def test_protocol_evaluate_accepts_keyword_only_max_attempts():
    import inspect

    param = inspect.signature(SystemOneClient.evaluate).parameters["max_attempts"]
    assert param.kind is inspect.Parameter.KEYWORD_ONLY
    assert param.default is None


class TestParseBar:
    def test_none_is_unset(self):
        assert parse_bar(None, "x", event="bar_invalid") is None

    def test_accepts_the_unit_interval(self):
        assert parse_bar(0, "x", event="bar_invalid") == 0.0
        assert parse_bar(1, "x", event="bar_invalid") == 1.0
        assert parse_bar(0.25, "x", event="bar_invalid") == 0.25

    @pytest.mark.parametrize("value", [True, "0.5", -0.1, 1.1, float("nan"), [0.5]])
    def test_rejects_everything_else(self, value):
        assert parse_bar(value, "x", event="bar_invalid") is None


class TestSurfaceBlock:
    def test_reads_a_plain_dict(self):
        cfg = {"system_one": {"surfaces": {"skills": {"enabled": True}}}}
        assert surface_block(cfg, "skills") == {"enabled": True}

    def test_reads_a_settings_object_config(self):
        cfg = {"system_one": {"surfaces": {"routing": {"enabled": True}}}}
        assert surface_block(SimpleNamespace(config=cfg), "routing") == {
            "enabled": True
        }

    @pytest.mark.parametrize(
        "settings",
        [
            None,
            object(),
            {},
            {"system_one": None},
            {"system_one": {"surfaces": None}},
            {"system_one": {"surfaces": {"skills": "on"}}},
            {"system_one": {"surfaces": {"other": {}}}},
        ],
    )
    def test_missing_or_malformed_is_none(self, settings):
        assert surface_block(settings, "skills") is None


def _noul(value):
    return SystemOneAnswer(type="noul", noul=value)


class TestValidNoul:
    @pytest.mark.parametrize("value", [0.0, 0.5, 1.0, 0, 1])
    def test_unit_values_pass(self, value):
        assert valid_noul(_noul(value))

    @pytest.mark.parametrize("value", [None, True, False, float("nan"), "0.5"])
    def test_non_numbers_never_pass(self, value):
        assert not valid_noul(_noul(value))
        assert not valid_noul(_noul(value), unit_range=False)

    @pytest.mark.parametrize("value", [-0.1, 1.2])
    def test_unit_range_is_the_default(self, value):
        assert not valid_noul(_noul(value))
        assert valid_noul(_noul(value), unit_range=False)

    def test_missing_or_wrong_type(self):
        assert not valid_noul(None)
        assert not valid_noul(SystemOneAnswer(type="choice", noul=0.5))


class TestValidChoice:
    def _choice(self, choice="a", confidence=0.8):
        return SystemOneAnswer(type="choice", choice=choice, confidence=confidence)

    def test_any_choice_when_no_options_given(self):
        assert valid_choice(self._choice("anything"))

    def test_choice_must_be_an_option(self):
        assert valid_choice(self._choice("a"), ["a", "b"])
        assert not valid_choice(self._choice("c"), ["a", "b"])

    def test_needs_choice_and_confidence(self):
        assert not valid_choice(self._choice(choice=None))
        assert not valid_choice(self._choice(confidence=None))
        assert not valid_choice(None)
        assert not valid_choice(SystemOneAnswer(type="noul", noul=0.5))
