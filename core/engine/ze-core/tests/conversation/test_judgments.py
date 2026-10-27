"""judgments_from_result — SystemOneResult → JudgmentTrace rows."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import ClassVar

from ze_agents.judgment import DecisionUse, SurfaceConfig, judge
from ze_agents.system_one import (
    SystemOneAnswer,
    SystemOneQuestion,
    SystemOneResult,
)

from ze_core.conversation.messages.judgments import (
    judgment_rows,
    judgments_from_result as _from_result,
)
from ze_core.conversation.messages.types import JudgmentBar

_IDS = ("speech_act", "family", "biography")
_KINDS = {"speech_act": "choice", "family": "choice", "biography": "noul"}

judgments_from_result = partial(_from_result, surface="routing", bars={})


def _ok() -> SystemOneResult:
    return SystemOneResult(
        outcome="ok",
        model="typesafe/jev-1.13-x",
        input_tokens=120,
        latency_ms=210,
        answers={
            "speech_act": SystemOneAnswer(
                type="choice",
                choice="fact",
                confidence=0.91,
                probabilities={"fact": 0.95, "drop": 0.05},
            ),
            "family": SystemOneAnswer(
                type="choice",
                choice="preference",
                confidence=0.8,
                probabilities={"preference": 0.9, "drop": 0.1},
            ),
            "biography": SystemOneAnswer(type="noul", noul=0.88),
        },
    )


def test_ok_result_gives_three_rows():
    rows = judgments_from_result(
        _ok(), question_kinds=_KINDS, consumed=frozenset({"speech_act", "family"})
    )
    by_id = {r.question_id: r for r in rows}
    assert set(by_id) == set(_IDS)
    act = by_id["speech_act"]
    assert (act.kind, act.answer, act.peakedness) == ("choice", "fact", 0.91)
    assert act.probabilities == {"fact": 0.95, "drop": 0.05}
    assert act.model == "typesafe/jev-1.13-x"
    assert act.input_tokens == 120
    assert act.latency_ms == 210
    bio = by_id["biography"]
    assert (bio.kind, bio.answer, bio.peakedness) == ("noul", 0.88, None)
    assert bio.probabilities is None
    assert act.consumed and by_id["family"].consumed and not bio.consumed
    assert all(r.skip_reason is None for r in rows)


def test_skip_result_gives_rows_per_question_id():
    result = SystemOneResult(outcome="skip", skip_reason="timeout", latency_ms=2000)
    rows = judgments_from_result(result, question_kinds=_KINDS, consumed=frozenset())
    assert [r.question_id for r in rows] == list(_IDS)
    assert all(r.answer is None and r.skip_reason == "timeout" for r in rows)
    assert all(not r.consumed for r in rows)
    assert all(r.latency_ms == 2000 for r in rows)


def test_skip_result_never_marks_consumed():
    result = SystemOneResult(outcome="skip", skip_reason="overload")
    rows = judgments_from_result(
        result, question_kinds=_KINDS, consumed=frozenset(_IDS)
    )
    assert all(not r.consumed for r in rows)


def test_decision_skip_reason_stamped_on_ok_rows():
    rows = judgments_from_result(
        _ok(),
        question_kinds=_KINDS,
        consumed=frozenset(),
        skip_reason="invalid_answer",
    )
    assert all(r.skip_reason == "invalid_answer" for r in rows)
    assert all(not r.consumed for r in rows)


def test_missing_answer_gets_its_own_skip_row():
    result = _ok()
    del result.answers["biography"]
    rows = judgments_from_result(
        result,
        question_kinds=_KINDS,
        consumed=frozenset(),
        skip_reason="invalid_answer",
    )
    assert [r.question_id for r in rows] == list(_IDS)
    bio = rows[-1]
    assert bio.answer is None and bio.kind == "noul"
    assert bio.skip_reason == "invalid_answer" and not bio.consumed


_ROUTING_KINDS = {
    "agent": "choice",
    "multi_specialist": "noul",
    "needs_deep_reasoning": "noul",
}


def test_skip_rows_take_kind_from_the_question_kinds_map():
    result = SystemOneResult(outcome="skip", skip_reason="timeout")
    rows = judgments_from_result(
        result, question_kinds=_ROUTING_KINDS, consumed=frozenset()
    )
    assert {r.question_id: r.kind for r in rows} == _ROUTING_KINDS


def test_ok_result_missing_noul_answer_gives_noul_skip_row():
    result = SystemOneResult(
        outcome="ok",
        answers={
            "agent": SystemOneAnswer(
                type="choice", choice="calendar", confidence=0.9, probabilities={}
            ),
            "multi_specialist": SystemOneAnswer(type="noul", noul=0.1),
        },
    )
    rows = judgments_from_result(
        result,
        question_kinds=_ROUTING_KINDS,
        consumed=frozenset(),
        skip_reason="invalid_answer",
    )
    deep = {r.question_id: r for r in rows}["needs_deep_reasoning"]
    assert deep.kind == "noul"
    assert deep.answer is None and deep.skip_reason == "invalid_answer"


def test_ok_noul_answer_carries_the_float_only():
    result = SystemOneResult(
        outcome="ok",
        model="jev",
        answers={"needs_deep_reasoning": SystemOneAnswer(type="noul", noul=0.42)},
    )
    rows = judgments_from_result(
        result,
        question_kinds={"needs_deep_reasoning": "noul"},
        consumed=frozenset({"needs_deep_reasoning"}),
    )
    (row,) = rows
    assert row.kind == "noul"
    assert row.answer == 0.42
    assert row.peakedness is None and row.probabilities is None
    assert row.consumed


def test_rows_carry_surface_and_the_bar_of_their_question():
    bars = {"agent": JudgmentBar("choice_trust", 0.5)}
    rows = _from_result(
        SystemOneResult(
            outcome="ok",
            answers={
                "agent": SystemOneAnswer(
                    type="choice", choice="calendar", confidence=0.9, probabilities={}
                ),
                "multi_specialist": SystemOneAnswer(type="noul", noul=0.1),
            },
        ),
        question_kinds={"agent": "choice", "multi_specialist": "noul"},
        consumed=frozenset(),
        surface="routing",
        bars=bars,
    )
    by_id = {r.question_id: r for r in rows}
    assert all(r.surface == "routing" for r in rows)
    assert by_id["agent"].bar == JudgmentBar("choice_trust", 0.5)
    assert by_id["multi_specialist"].bar is None


def test_skip_rows_carry_surface_and_bar():
    rows = _from_result(
        SystemOneResult(outcome="skip", skip_reason="timeout"),
        question_kinds={"agent": "choice"},
        consumed=frozenset(),
        surface="routing",
        bars={"agent": JudgmentBar("choice_trust", 0.5)},
    )
    assert rows[0].surface == "routing" and rows[0].bar.value == 0.5


# --- judgment_rows: the record alone is enough ---------------------------------


@dataclass(frozen=True)
class _Demo(SurfaceConfig):
    enabled: bool = False
    pick_trust: float | None = None
    flag_hold: float | None = None

    SURFACE: ClassVar[str] = "demo"
    BARS: ClassVar[dict[str, str]] = {"pick_trust": "pick", "flag_hold": "flag"}
    EXTRAS: ClassVar[dict] = {}


_DEMO_QUESTIONS = {
    "pick": SystemOneQuestion(type="choice", instructions="Pick one"),
    "flag": SystemOneQuestion(type="noul", instructions="Is it flagged?"),
}


class _Client:
    def __init__(self, result: SystemOneResult | Exception) -> None:
        self._result = result

    async def evaluate(self, state, questions, *, max_attempts=None):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _demo_ok() -> SystemOneResult:
    return SystemOneResult(
        outcome="ok",
        model="m",
        input_tokens=50,
        latency_ms=33,
        answers={
            "pick": SystemOneAnswer(
                type="choice",
                choice="x",
                confidence=0.8,
                probabilities={"x": 0.9, "y": 0.1},
            ),
            "flag": SystemOneAnswer(type="noul", noul=0.2),
        },
    )


def _consume(consumed: frozenset[str], reason: str | None = None):
    return lambda _decision: DecisionUse(consumed=consumed, unused_reason=reason)


async def _record(
    result: SystemOneResult | Exception,
    cfg: _Demo,
    consumed: frozenset[str] = frozenset(),
    reason: str | None = None,
):
    record, _ = await judge(
        _Client(result),
        cfg,
        "state",
        _DEMO_QUESTIONS,
        lambda r: r,
        _consume(consumed, reason),
    )
    return record


_BARRED = _Demo(enabled=True, pick_trust=0.5, flag_hold=0.7)


async def test_rows_for_an_ok_result_carry_answers_consumed_and_bars():
    record = await _record(_demo_ok(), _BARRED, frozenset({"pick"}))
    rows = {r.question_id: r for r in judgment_rows(record)}
    assert list(rows) == ["pick", "flag"]
    pick, flag = rows["pick"], rows["flag"]
    assert (pick.kind, pick.answer, pick.peakedness) == ("choice", "x", 0.8)
    assert pick.probabilities == {"x": 0.9, "y": 0.1}
    assert (pick.model, pick.input_tokens, pick.latency_ms) == ("m", 50, 33)
    assert pick.consumed is True and flag.consumed is False
    assert flag.answer == 0.2 and flag.probabilities is None
    assert pick.surface == flag.surface == "demo"
    assert pick.bar == JudgmentBar("pick_trust", 0.5)
    assert flag.bar == JudgmentBar("flag_hold", 0.7)
    assert pick.skip_reason is None


async def test_rows_for_a_skip_result_use_the_record_skip_reason():
    record = await _record(
        SystemOneResult(outcome="skip", skip_reason="timeout", latency_ms=9), _BARRED
    )
    rows = judgment_rows(record)
    assert [r.question_id for r in rows] == ["pick", "flag"]
    assert [r.kind for r in rows] == ["choice", "noul"]
    for row in rows:
        assert row.skip_reason == "timeout"
        assert row.surface == "demo"
        assert row.latency_ms == 9
        assert row.answer is None and row.consumed is False
    assert rows[0].bar == JudgmentBar("pick_trust", 0.5)


async def test_rows_for_a_raised_call_say_error():
    record = await _record(RuntimeError("boom"), _BARRED)
    rows = judgment_rows(record)
    assert [r.skip_reason for r in rows] == ["error", "error"]


async def test_an_ok_result_missing_one_answer_gives_that_question_a_skip_row():
    result = _demo_ok()
    del result.answers["flag"]
    record = await _record(
        result, _BARRED, frozenset({"pick"}), reason="invalid_answer"
    )
    rows = {r.question_id: r for r in judgment_rows(record)}
    assert rows["flag"].answer is None
    assert rows["flag"].skip_reason == "invalid_answer"
    assert rows["flag"].kind == "noul"
    assert rows["pick"].answer == "x"


async def test_an_unset_bar_gives_bar_none():
    cfg = _Demo(enabled=True, pick_trust=0.5)
    record = await _record(_demo_ok(), cfg)
    rows = {r.question_id: r for r in judgment_rows(record)}
    assert rows["pick"].bar == JudgmentBar("pick_trust", 0.5)
    assert rows["flag"].bar is None
