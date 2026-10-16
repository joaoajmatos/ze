"""judgments_from_result — SystemOneResult → JudgmentTrace rows."""

from __future__ import annotations

from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_core.conversation.messages.judgments import judgments_from_result

_IDS = ("speech_act", "family", "biography")
_KINDS = {"speech_act": "choice", "family": "choice", "biography": "noul"}


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
