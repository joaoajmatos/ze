"""Routing judgment — surface config, questions, shortlist, state, decide()."""

from __future__ import annotations

from ze_core.routing.judge import (
    HISTORY_CAP,
    CONTEXT_CAP,
    USER_CAP,
    RoutingSurfaceConfig,
    build_questions,
    build_state,
    routing_surface_config,
    shortlist,
)


def _settings(block) -> dict:
    return {"config": {"system_one": {"surfaces": {"routing": block}}}}


class _Settings:
    def __init__(self, config) -> None:
        self.config = config


def _cfg(block) -> RoutingSurfaceConfig:
    return routing_surface_config(_Settings(_settings(block)["config"]))


class TestSurfaceConfig:
    def test_missing_block_is_disabled(self):
        assert not routing_surface_config({}).enabled
        assert not routing_surface_config(None).enabled
        assert not routing_surface_config(_Settings({})).calibrated

    def test_invalid_block_is_disabled(self):
        cfg = routing_surface_config({"system_one": {"surfaces": {"routing": "on"}}})
        assert cfg == RoutingSurfaceConfig()

    def test_dict_and_settings_are_both_accepted(self):
        block = {"enabled": True, "choice_trust": 0.8, "multi_specialist_hold": 0.6}
        as_dict = routing_surface_config(_settings(block)["config"])
        as_obj = routing_surface_config(_Settings(_settings(block)["config"]))
        assert as_dict == as_obj
        assert as_dict.calibrated

    def test_enabled_with_null_bar_is_not_calibrated(self):
        cfg = _cfg({"enabled": True, "choice_trust": 0.8, "multi_specialist_hold": None})
        assert cfg.enabled and not cfg.calibrated

    def test_disabled_with_bars_is_not_calibrated(self):
        cfg = _cfg({"enabled": False, "choice_trust": 0.8, "multi_specialist_hold": 0.6})
        assert not cfg.calibrated

    def test_bad_bars_become_none(self):
        cfg = _cfg(
            {
                "enabled": True,
                "choice_trust": "high",
                "multi_specialist_hold": float("nan"),
                "complexity_lookup_max": 1.5,
            }
        )
        assert cfg.choice_trust is None
        assert cfg.multi_specialist_hold is None
        assert cfg.complexity_lookup_max is None

    def test_bool_is_not_a_bar(self):
        assert _cfg({"enabled": True, "choice_trust": True}).choice_trust is None

    def test_shortlist_k_defaults_and_falls_back(self):
        assert _cfg({}).shortlist_k == 4
        assert _cfg({"shortlist_k": 1}).shortlist_k == 4
        assert _cfg({"shortlist_k": "3"}).shortlist_k == 4
        assert _cfg({"shortlist_k": True}).shortlist_k == 4
        assert _cfg({"shortlist_k": 6}).shortlist_k == 6

    def test_enabled_must_be_literally_true(self):
        assert not _cfg({"enabled": "yes"}).enabled


class TestQuestions:
    def test_three_questions_with_expected_kinds(self):
        qs = build_questions({"calendar": " Calendar stuff ", "messenger": "Mail"})
        assert list(qs) == ["agent", "multi_specialist", "complexity"]
        assert qs["agent"].type == "choice"
        assert qs["multi_specialist"].type == "noul"
        assert qs["complexity"].type == "score"

    def test_agent_criteria_is_shortlist_plus_none(self):
        qs = build_questions({"calendar": " Calendar stuff ", "messenger": "Mail"})
        criteria = qs["agent"].criteria
        assert list(criteria) == ["calendar", "messenger", "none"]
        assert criteria["calendar"] == "Calendar stuff"
        assert criteria["none"]

    def test_complexity_levels_are_ordered(self):
        qs = build_questions({"a": "x", "b": "y"})
        levels = qs["complexity"].criteria
        assert isinstance(levels, list)
        assert [lv.split(":")[0] for lv in levels] == [
            "lookup",
            "single_tool",
            "multi_hop",
        ]

    def test_instructions_say_user_words_judge(self):
        qs = build_questions({"a": "x", "b": "y"})
        for q in qs.values():
            assert q.instructions.rstrip().endswith(
                "Judge the user's words; history and context are background only."
            )


class TestShortlist:
    def test_top_k_in_rank_order(self):
        assert shortlist(["a", "b", "c", "d", "e"], 3) == ["a", "b", "c"]

    def test_clamped_to_enabled_count(self):
        assert shortlist(["a", "b", "c"], 9) == ["a", "b", "c"]

    def test_never_fewer_than_two_when_two_exist(self):
        assert shortlist(["a", "b", "c"], 1) == ["a", "b"]
        assert shortlist(["a", "b"], 0) == ["a", "b"]

    def test_single_agent(self):
        assert shortlist(["a"], 4) == ["a"]


class TestState:
    def test_user_is_capped(self):
        state = build_state("x" * (USER_CAP + 50), None, None)
        assert len(state["user"]) == USER_CAP

    def test_context_is_capped(self):
        state = build_state("hi", None, "c" * (CONTEXT_CAP + 50))
        assert len(state["context"]) == CONTEXT_CAP

    def test_empty_parts_are_dropped(self):
        assert build_state("hi", None, None) == {"user": "hi"}
        assert build_state("hi", "", "  ") == {"user": "hi"}

    def test_history_kept_separate_and_capped(self):
        state = build_state("hi", "[Recent conversation]\nuser: a", "ctx")
        assert state["user"] == "hi"
        assert state["history"].startswith("[Recent conversation]")
        assert state["context"] == "ctx"
        long_state = build_state("hi", "h" * (HISTORY_CAP + 10), None)
        assert len(long_state["history"]) == HISTORY_CAP
