"""Tests for the shared judgment-surface module."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

import pytest

from ze_agents import judgment as judgment_module
from ze_agents.judgment import (
    DecisionUse,
    Judgment,
    SurfaceBar,
    SurfaceConfig,
    gate,
    judge,
    parse_bar,
    reset_surface_warnings,
    surface_block,
)
from ze_agents.system_one import (
    SystemOneAnswer,
    SystemOneQuestion,
    SystemOneResult,
)


def _int_parser(raw: Any) -> int:
    if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 1:
        return raw
    return 3


@dataclass(frozen=True)
class _Demo(SurfaceConfig):
    enabled: bool = False
    a_hold: float | None = None
    b_hold: float | None = None
    k: int = 3

    SURFACE: ClassVar[str] = "demo"
    BARS: ClassVar[dict[str, str]] = {"a_hold": "a", "b_hold": "b"}
    EXTRAS: ClassVar[dict[str, Callable[[Any], Any]]] = {"k": _int_parser}


@dataclass(frozen=True)
class _Ordered(_Demo):
    SURFACE: ClassVar[str] = "ordered"

    def consistent(self) -> bool:
        return (
            self.a_hold is not None
            and self.b_hold is not None
            and self.a_hold <= self.b_hold
        )


@dataclass(frozen=True)
class _TwoBarsOneQuestion(SurfaceConfig):
    enabled: bool = False
    first: float | None = None
    second: float | None = None

    SURFACE: ClassVar[str] = "twobars"
    BARS: ClassVar[dict[str, str]] = {"first": "q", "second": "q"}
    EXTRAS: ClassVar[dict[str, Callable[[Any], Any]]] = {}


QUESTIONS = {
    "a": SystemOneQuestion(type="noul", instructions="Is a true?"),
    "b": SystemOneQuestion(type="noul", instructions="Is b true?"),
}


def _decide(result: SystemOneResult) -> str:
    return "used" if result.outcome == "ok" else "skipped"


def _read_used(decision: str) -> DecisionUse:
    return DecisionUse(consumed=frozenset({"a"}))


def _read_unused(decision: str) -> DecisionUse:
    return DecisionUse(consumed=frozenset(), unused_reason="invalid_answer")


class _Client:
    def __init__(self, result: SystemOneResult | Exception) -> None:
        self._result = result
        self.calls: list[tuple[Any, dict, int | None]] = []

    async def evaluate(
        self,
        state: Any,
        questions: dict[str, SystemOneQuestion],
        *,
        max_attempts: int | None = None,
    ) -> SystemOneResult:
        self.calls.append((state, questions, max_attempts))
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _ok() -> SystemOneResult:
    return SystemOneResult(
        outcome="ok",
        answers={
            "a": SystemOneAnswer(type="noul", noul=0.9),
            "b": SystemOneAnswer(type="noul", noul=0.1),
        },
    )


@pytest.fixture(autouse=True)
def _fresh_warnings() -> None:
    reset_surface_warnings()


@pytest.fixture
def log() -> MagicMock:
    with patch.object(judgment_module, "log") as mock:
        yield mock


def _events(log: MagicMock, level: str) -> list[tuple[str, dict]]:
    return [(c.args[0], c.kwargs) for c in getattr(log, level).call_args_list]


# --- surface_block / parse_bar -------------------------------------------------


def test_surface_block_reads_a_settings_object_config() -> None:
    cfg = {"system_one": {"surfaces": {"routing": {"enabled": True}}}}
    assert surface_block(SimpleNamespace(config=cfg), "routing") == {"enabled": True}


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
def test_surface_block_missing_or_malformed_is_none(settings: Any) -> None:
    assert surface_block(settings, "skills") is None


def test_surface_block_reads_dict_and_settings_object() -> None:
    config = {"system_one": {"surfaces": {"demo": {"enabled": True}}}}
    assert surface_block(config, "demo") == {"enabled": True}
    holder = MagicMock()
    holder.config = config
    assert surface_block(holder, "demo") == {"enabled": True}
    assert surface_block(config, "other") is None
    assert surface_block({"system_one": []}, "demo") is None
    assert surface_block(object(), "demo") is None


def test_parse_bar_accepts_unit_range_and_rejects_the_rest(log: MagicMock) -> None:
    assert parse_bar(None, "x", surface="demo") is None
    assert parse_bar(0, "x", surface="demo") == 0.0
    assert parse_bar(1, "x", surface="demo") == 1.0
    assert parse_bar(0.25, "x", surface="demo") == 0.25
    assert not _events(log, "warning")
    for bad in (-0.1, 1.5, 1.1, True, "0.5", float("nan"), [0.5]):
        assert parse_bar(bad, "x", surface="demo") is None


# --- from_settings --------------------------------------------------------------


def test_from_settings_missing_block_gives_defaults() -> None:
    assert _Demo.from_settings({}) == _Demo()
    assert _Demo.from_settings({"system_one": {"surfaces": {}}}) == _Demo()


@pytest.mark.parametrize("enabled", [1, "true", "yes", None, 0])
def test_enabled_only_for_literal_true(enabled: Any) -> None:
    cfg = _Demo.from_settings(
        {"system_one": {"surfaces": {"demo": {"enabled": enabled}}}}
    )
    assert cfg.enabled is False


def test_from_settings_parses_bars_and_extras() -> None:
    cfg = _Demo.from_settings(
        {
            "system_one": {
                "surfaces": {
                    "demo": {"enabled": True, "a_hold": 0.6, "b_hold": 1, "k": 7}
                }
            }
        }
    )
    assert cfg == _Demo(enabled=True, a_hold=0.6, b_hold=1.0, k=7)


def test_from_settings_extra_parser_supplies_default_for_invalid() -> None:
    cfg = _Demo.from_settings(
        {"system_one": {"surfaces": {"demo": {"enabled": True, "k": "x"}}}}
    )
    assert cfg.k == 3


@pytest.mark.parametrize("bad", [-0.5, 1.5, True, "0.7", float("nan")])
def test_invalid_bar_becomes_none(bad: Any, log: MagicMock) -> None:
    cfg = _Demo.from_settings(
        {"system_one": {"surfaces": {"demo": {"enabled": True, "a_hold": bad}}}}
    )
    assert cfg.a_hold is None
    assert not cfg.calibrated


def test_invalid_bar_logs_once_per_surface_and_bar(log: MagicMock) -> None:
    settings = {"system_one": {"surfaces": {"demo": {"enabled": True, "a_hold": 5}}}}
    _Demo.from_settings(settings)
    _Demo.from_settings(settings)
    events = [e for e in _events(log, "warning") if e[0] == "system_one_bar_invalid"]
    assert events == [("system_one_bar_invalid", {"surface": "demo", "bar": "a_hold"})]


def test_from_settings_works_on_object_with_config() -> None:
    holder = MagicMock()
    holder.config = {
        "system_one": {"surfaces": {"demo": {"enabled": True, "a_hold": 0.5}}}
    }
    assert _Demo.from_settings(holder).a_hold == 0.5


# --- calibrated / bar_for --------------------------------------------------------


def test_calibrated_needs_enabled_and_every_bar() -> None:
    assert not _Demo(a_hold=0.5, b_hold=0.5).calibrated
    assert not _Demo(enabled=True, a_hold=0.5).calibrated
    assert _Demo(enabled=True, a_hold=0.5, b_hold=0.5).calibrated


def test_calibrated_honours_consistency_check() -> None:
    assert _Ordered(enabled=True, a_hold=0.4, b_hold=0.6).calibrated
    assert not _Ordered(enabled=True, a_hold=0.8, b_hold=0.6).calibrated


def test_bar_for_returns_surface_bar_or_none() -> None:
    cfg = _Demo(enabled=True, a_hold=0.5)
    assert cfg.bar_for("a") == SurfaceBar("a_hold", 0.5)
    assert cfg.bar_for("b") is None
    assert cfg.bar_for("unknown") is None


def test_bar_for_first_bar_in_order_wins_for_a_shared_question() -> None:
    cfg = _TwoBarsOneQuestion(enabled=True, first=0.3, second=0.9)
    assert cfg.bar_for("q") == SurfaceBar("first", 0.3)


# --- gate -------------------------------------------------------------------------


def test_gate_order(log: MagicMock) -> None:
    client = _Client(_ok())
    assert gate(_Demo(), client) == "disabled"
    assert not _events(log, "warning")
    assert gate(_Demo(enabled=True, a_hold=0.5), client) == "uncalibrated"
    cfg = _Demo(enabled=True, a_hold=0.5, b_hold=0.5)
    assert gate(cfg, None) == "unavailable"
    assert gate(cfg, client) is None


def test_gate_warns_uncalibrated_once_per_surface(log: MagicMock) -> None:
    cfg = _Demo(enabled=True)
    gate(cfg, None)
    gate(cfg, None)
    uncalibrated = [
        e for e in _events(log, "warning") if e[0] == "system_one_surface_uncalibrated"
    ]
    assert uncalibrated == [("system_one_surface_uncalibrated", {"surface": "demo"})]
    gate(_Ordered(enabled=True), None)
    uncalibrated = [
        e for e in _events(log, "warning") if e[0] == "system_one_surface_uncalibrated"
    ]
    assert len(uncalibrated) == 2

    reset_surface_warnings()
    gate(cfg, None)
    uncalibrated = [
        e for e in _events(log, "warning") if e[0] == "system_one_surface_uncalibrated"
    ]
    assert len(uncalibrated) == 3


# --- judge ------------------------------------------------------------------------

CAL = _Demo(enabled=True, a_hold=0.6, b_hold=0.7)


async def test_judge_makes_one_single_attempt_call() -> None:
    client = _Client(_ok())
    record, decision = await judge(client, CAL, "state", QUESTIONS, _decide, _read_used)
    assert client.calls == [("state", QUESTIONS, 1)]
    assert decision == "used"
    assert isinstance(record, Judgment)


async def test_judge_record_carries_surface_kinds_consumed_and_bars() -> None:
    record, _ = await judge(
        _Client(_ok()), CAL, "state", QUESTIONS, _decide, _read_used
    )
    assert record.surface == "demo"
    assert record.result.outcome == "ok"
    assert list(record.question_kinds) == ["a", "b"]
    assert record.question_kinds == {"a": "noul", "b": "noul"}
    assert record.consumed == frozenset({"a"})
    assert record.skip_reason is None
    assert record.bars == {
        "a": SurfaceBar("a_hold", 0.6),
        "b": SurfaceBar("b_hold", 0.7),
    }


async def test_judge_bars_hold_none_for_unset_bars() -> None:
    cfg = _Demo(enabled=True, a_hold=0.6)
    record, _ = await judge(_Client(_ok()), cfg, "s", QUESTIONS, _decide, _read_used)
    assert record.bars == {"a": SurfaceBar("a_hold", 0.6), "b": None}


async def test_judge_exception_becomes_error_skip(log: MagicMock) -> None:
    client = _Client(RuntimeError("boom"))
    record, decision = await judge(client, CAL, "s", QUESTIONS, _decide, _read_used)
    assert record.result == SystemOneResult(outcome="skip", skip_reason="error")
    assert record.skip_reason == "error"
    assert decision == "skipped"
    events = _events(log, "warning")
    assert [e[0] for e in events] == ["system_one_judgment_error"]
    assert events[0][1]["surface"] == "demo"
    assert "boom" in events[0][1]["error"]


async def test_judge_client_skip_reason_wins_over_decision_reason() -> None:
    client = _Client(SystemOneResult(outcome="skip", skip_reason="timeout"))
    record, _ = await judge(client, CAL, "s", QUESTIONS, _decide, _read_unused)
    assert record.skip_reason == "timeout"


async def test_judge_skip_without_reason_stays_none() -> None:
    client = _Client(SystemOneResult(outcome="skip"))
    record, _ = await judge(client, CAL, "s", QUESTIONS, _decide, _read_unused)
    assert record.skip_reason is None


async def test_judge_ok_result_takes_decision_unused_reason() -> None:
    record, _ = await judge(_Client(_ok()), CAL, "s", QUESTIONS, _decide, _read_unused)
    assert record.skip_reason == "invalid_answer"
    assert record.consumed == frozenset()


async def test_judge_ok_and_used_has_no_skip_reason() -> None:
    record, _ = await judge(_Client(_ok()), CAL, "s", QUESTIONS, _decide, _read_used)
    assert record.skip_reason is None
