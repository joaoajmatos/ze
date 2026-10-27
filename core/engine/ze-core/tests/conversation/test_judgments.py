"""judgment_rows — Judgment record → JudgmentTrace rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from ze_agents.judgment import DecisionUse, SurfaceConfig, judge
from ze_agents.system_one import (
    SystemOneAnswer,
    SystemOneQuestion,
    SystemOneResult,
)

from ze_core.conversation.messages.judgments import judgment_rows
from ze_core.conversation.messages.types import JudgmentBar

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
