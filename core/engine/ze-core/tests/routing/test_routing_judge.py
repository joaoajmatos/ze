"""Routing judgment — surface config, questions, shortlist, state, decide()."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace


from ze_core.routing.judge import (
    HISTORY_CAP,
    CONTEXT_CAP,
    USER_CAP,
    RoutingSurfaceConfig,
    build_questions,
    criterion_for,
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
        cfg = _cfg(
            {"enabled": True, "choice_trust": 0.8, "multi_specialist_hold": None}
        )
        assert cfg.enabled and not cfg.calibrated

    def test_disabled_with_bars_is_not_calibrated(self):
        cfg = _cfg(
            {"enabled": False, "choice_trust": 0.8, "multi_specialist_hold": 0.6}
        )
        assert not cfg.calibrated

    def test_bad_bars_become_none(self):
        cfg = _cfg(
            {
                "enabled": True,
                "choice_trust": "high",
                "multi_specialist_hold": float("nan"),
            }
        )
        assert cfg.choice_trust is None
        assert cfg.multi_specialist_hold is None

    def test_surface_has_no_complexity_lookup_max(self):
        assert not hasattr(RoutingSurfaceConfig(), "complexity_lookup_max")
        cfg = _cfg(
            {
                "enabled": True,
                "choice_trust": 0.8,
                "multi_specialist_hold": 0.6,
                "complexity_lookup_max": 0.3,
            }
        )
        assert not hasattr(cfg, "complexity_lookup_max")

    def test_bool_is_not_a_bar(self):
        assert _cfg({"enabled": True, "choice_trust": True}).choice_trust is None

    def test_shortlist_k_defaults_and_falls_back(self):
        assert _cfg({}).shortlist_k == 5
        assert _cfg({"shortlist_k": 1}).shortlist_k == 5
        assert _cfg({"shortlist_k": "3"}).shortlist_k == 5
        assert _cfg({"shortlist_k": True}).shortlist_k == 5
        assert _cfg({"shortlist_k": 6}).shortlist_k == 6

    def test_enabled_must_be_literally_true(self):
        assert not _cfg({"enabled": "yes"}).enabled


class TestQuestions:
    def test_two_questions_with_expected_kinds(self):
        qs = build_questions({"calendar": " Calendar stuff ", "messenger": "Mail"})
        assert list(qs) == ["agent", "multi_specialist"]
        assert qs["agent"].type == "choice"
        assert qs["multi_specialist"].type == "noul"

    def test_agent_criteria_is_shortlist_plus_none(self):
        qs = build_questions({"calendar": " Calendar stuff ", "messenger": "Mail"})
        criteria = qs["agent"].criteria
        assert list(criteria) == ["calendar", "messenger", "none"]
        assert criteria["calendar"] == "Calendar stuff"
        assert criteria["none"]

    def test_instructions_say_user_words_judge(self):
        qs = build_questions({"a": "x", "b": "y"})
        for q in qs.values():
            assert q.instructions.rstrip().endswith(
                "Judge the user's words; history and context are background only."
            )


class TestCriteria:
    def test_each_text_reaches_the_choice_in_order(self):
        qs = build_questions({"b": "Use for: x", "a": "Use for: y"})
        assert list(qs["agent"].criteria) == ["b", "a", "none"]
        assert qs["agent"].criteria["b"] == "Use for: x"

    def test_criterion_prefers_routing_criteria(self):
        cls = SimpleNamespace(description=" D ", routing_criteria=" Use for: z ")
        assert criterion_for(cls) == "Use for: z"

    def test_criterion_falls_back_to_description(self):
        assert (
            criterion_for(SimpleNamespace(description=" D ", routing_criteria=""))
            == "D"
        )
        assert criterion_for(SimpleNamespace(description=" D ")) == "D"

    def test_judge_module_names_no_plugin_agent(self):
        import ze_core.routing.judge as judge

        tree = ast.parse(Path(judge.__file__).read_text(encoding="utf-8"))
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef))
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        }
        literals = " ".join(
            node.value.lower()
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        )
        for name in ("companion", "research", "calendar", "messenger"):
            assert name not in literals

    def test_instructions_prefer_tool_agents_for_factual_requests(self):
        qs = build_questions({"a": "x", "b": "y"})
        assert "searches the web" in qs["agent"].instructions
        assert "more than one agent" in qs["agent"].criteria["none"]


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


# ── decide() ──────────────────────────────────────────────────────────────────

from ze_agents.system_one import SystemOneResult  # noqa: E402
from tests.support.routing import choice_answer, ok_result  # noqa: E402
from ze_core.routing.judge import decide  # noqa: E402

_SHORT = ["calendar", "messenger"]
_CAL = RoutingSurfaceConfig(
    enabled=True, choice_trust=0.8, multi_specialist_hold=0.6, shortlist_k=4
)


class TestDecideTrustAndSkip:
    def test_confident_choice_with_low_noul_is_trust(self):
        d = decide(
            ok_result(choice="calendar", peakedness=0.95, noul=0.1), _CAL, _SHORT
        )
        assert d.kind == "trust"
        assert d.agent == "calendar"
        assert d.reason == "trusted"
        assert d.confidence == 0.95
        assert d.consumed == frozenset({"agent", "multi_specialist"})

    def test_choice_exactly_at_bar_is_trusted(self):
        d = decide(ok_result(choice="calendar", peakedness=0.8, noul=0.1), _CAL, _SHORT)
        assert d.kind == "trust"

    def test_client_skip_keeps_its_reason(self):
        result = SystemOneResult(outcome="skip", skip_reason="timeout")
        d = decide(result, _CAL, _SHORT)
        assert (d.kind, d.reason) == ("skip", "timeout")
        assert d.consumed == frozenset()

    def test_missing_choice_is_invalid_answer(self):
        d = decide(ok_result(choice=None, noul=0.1), _CAL, _SHORT)
        assert (d.kind, d.reason) == ("skip", "invalid_answer")

    def test_unknown_agent_is_invalid_answer(self):
        d = decide(ok_result(choice="finance", peakedness=0.99), _CAL, _SHORT)
        assert (d.kind, d.reason) == ("skip", "invalid_answer")

    def test_null_confidence_is_invalid_answer(self):
        result = ok_result(choice="calendar")
        result.answers["agent"].confidence = None
        assert decide(result, _CAL, _SHORT).reason == "invalid_answer"

    def test_wrong_answer_type_is_invalid_answer(self):
        result = ok_result(choice="calendar")
        result.answers["agent"] = result.answers["multi_specialist"]
        assert decide(result, _CAL, _SHORT).reason == "invalid_answer"

    def test_uncalibrated_bar_skips(self):
        cfg = RoutingSurfaceConfig(enabled=True, choice_trust=None)
        d = decide(ok_result(choice="calendar"), cfg, _SHORT)
        assert (d.kind, d.reason) == ("skip", "uncalibrated")

    def test_choice_bar_does_not_read_noul_and_vice_versa(self):
        # Noul above the Choice bar but below its own hold bar must not decompose.
        cfg = RoutingSurfaceConfig(
            enabled=True, choice_trust=0.3, multi_specialist_hold=0.99
        )
        d = decide(ok_result(choice="calendar", peakedness=0.5, noul=0.9), cfg, _SHORT)
        assert d.kind == "trust"
        # Peakedness above the Noul hold bar must not matter to the Noul gate.
        cfg = RoutingSurfaceConfig(
            enabled=True, choice_trust=0.9, multi_specialist_hold=0.1
        )
        d = decide(ok_result(choice="calendar", peakedness=0.5, noul=0.05), cfg, _SHORT)
        assert d.kind == "abstain"

    def test_never_raises_on_garbage(self):
        result = SystemOneResult(outcome="ok", answers={"agent": choice_answer("x", 1)})
        result.answers["agent"].choice = None
        assert decide(result, _CAL, _SHORT).kind == "skip"


class TestDecideNoneAndUnsure:
    def test_none_at_high_peakedness_decomposes(self):
        d = decide(ok_result(choice="none", peakedness=0.95), _CAL, _SHORT)
        assert (d.kind, d.reason) == ("decompose", "choice_none")
        assert d.confidence == 0.95
        assert d.agent is None
        assert d.consumed == frozenset({"agent"})

    def test_none_at_low_peakedness_still_decomposes(self):
        d = decide(ok_result(choice="none", peakedness=0.2), _CAL, _SHORT)
        assert (d.kind, d.reason) == ("decompose", "choice_none")

    def test_choice_below_bar_abstains_and_consumes_nothing(self):
        d = decide(ok_result(choice="calendar", peakedness=0.5), _CAL, _SHORT)
        assert (d.kind, d.reason) == ("abstain", "choice_unsure")
        assert d.consumed == frozenset()
        assert d.confidence is None and d.agent is None


class TestDecideMultiSpecialistAndScore:
    def test_noul_at_hold_bar_decomposes(self):
        d = decide(ok_result(choice="calendar", noul=0.6), _CAL, _SHORT)
        assert (d.kind, d.reason) == ("decompose", "multi_specialist")
        assert d.consumed == frozenset({"agent", "multi_specialist"})
        assert d.confidence == 0.95

    def test_noul_below_hold_bar_is_trust(self):
        d = decide(ok_result(choice="calendar", noul=0.59), _CAL, _SHORT)
        assert d.kind == "trust"

    def test_noul_missing_is_trust_and_unconsumed(self):
        d = decide(ok_result(choice="calendar", noul=None), _CAL, _SHORT)
        assert d.kind == "trust"
        assert d.consumed == frozenset({"agent"})

    def test_noul_is_not_read_when_choice_is_none_or_unsure(self):
        none = decide(ok_result(choice="none", noul=0.99), _CAL, _SHORT)
        unsure = decide(
            ok_result(choice="calendar", peakedness=0.1, noul=0.99), _CAL, _SHORT
        )
        assert "multi_specialist" not in none.consumed
        assert "multi_specialist" not in unsure.consumed


class TestShippedConfig:
    def test_routing_surface_is_never_half_enabled(self):
        import yaml

        path = Path(__file__).resolve().parents[5] / "apps/ze-api/config/config.yaml"
        block = yaml.safe_load(path.read_text())["system_one"]["surfaces"]["routing"]
        cfg = routing_surface_config(yaml.safe_load(path.read_text()))
        if block["enabled"] is True:
            assert cfg.choice_trust is not None
            assert cfg.multi_specialist_hold is not None
        else:
            assert block["enabled"] is False
