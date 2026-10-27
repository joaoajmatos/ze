"""Convert System One results into trace judgment rows."""

from __future__ import annotations

from collections.abc import Mapping

from ze_agents.judgment import Judgment
from ze_agents.system_one import SystemOneAnswer, SystemOneResult

from ze_core.conversation.messages.types import JudgmentBar, JudgmentTrace


def judgment_rows(judgment: Judgment) -> list[JudgmentTrace]:
    result = judgment.result
    bars = {
        qid: None if bar is None else JudgmentBar(bar.name, bar.value)
        for qid, bar in judgment.bars.items()
    }
    rows: list[JudgmentTrace] = []
    for qid, kind in judgment.question_kinds.items():
        answer = result.answers.get(qid) if result.outcome == "ok" else None
        if answer is None:
            rows.append(
                JudgmentTrace(
                    question_id=qid,
                    kind=kind,
                    latency_ms=result.latency_ms,
                    skip_reason=judgment.skip_reason,
                    surface=judgment.surface,
                    bar=bars.get(qid),
                )
            )
            continue
        is_choice = answer.type == "choice"
        rows.append(
            JudgmentTrace(
                question_id=qid,
                kind=answer.type,
                latency_ms=result.latency_ms,
                answer=_answer_value(answer),
                probabilities=answer.probabilities if is_choice else None,
                peakedness=answer.confidence if is_choice else None,
                model=result.model,
                input_tokens=result.input_tokens,
                consumed=qid in judgment.consumed,
                skip_reason=judgment.skip_reason,
                surface=judgment.surface,
                bar=bars.get(qid),
            )
        )
    return rows


def judgments_from_result(
    result: SystemOneResult,
    *,
    question_kinds: Mapping[str, str],
    consumed: frozenset[str],
    skip_reason: str | None = None,
    surface: str,
    bars: Mapping[str, JudgmentBar | None],
) -> list[JudgmentTrace]:
    if result.outcome != "ok":
        reason = result.skip_reason or skip_reason
        return [
            JudgmentTrace(
                question_id=qid,
                kind=kind,
                latency_ms=result.latency_ms,
                skip_reason=reason,
                surface=surface,
                bar=bars.get(qid),
            )
            for qid, kind in question_kinds.items()
        ]
    rows: list[JudgmentTrace] = []
    for qid, kind in question_kinds.items():
        answer = result.answers.get(qid)
        if answer is None:
            rows.append(
                JudgmentTrace(
                    question_id=qid,
                    kind=kind,
                    latency_ms=result.latency_ms,
                    skip_reason=skip_reason,
                    surface=surface,
                    bar=bars.get(qid),
                )
            )
            continue
        is_choice = answer.type == "choice"
        rows.append(
            JudgmentTrace(
                question_id=qid,
                kind=answer.type,
                latency_ms=result.latency_ms,
                answer=_answer_value(answer),
                probabilities=answer.probabilities if is_choice else None,
                peakedness=answer.confidence if is_choice else None,
                model=result.model,
                input_tokens=result.input_tokens,
                consumed=qid in consumed,
                skip_reason=skip_reason,
                surface=surface,
                bar=bars.get(qid),
            )
        )
    return rows


def _answer_value(answer: SystemOneAnswer) -> str | float | None:
    if answer.type == "noul":
        return answer.noul
    if answer.type == "score":
        return answer.score
    return answer.choice
