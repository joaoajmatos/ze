"""Convert System One results into trace judgment rows."""

from __future__ import annotations

from collections.abc import Sequence

from ze_agents.system_one import SystemOneResult

from ze_core.conversation.messages.types import JudgmentTrace


def judgments_from_result(
    result: SystemOneResult,
    *,
    question_ids: Sequence[str],
    consumed: frozenset[str],
    skip_reason: str | None = None,
) -> list[JudgmentTrace]:
    if result.outcome != "ok":
        reason = result.skip_reason or skip_reason
        return [
            JudgmentTrace(
                question_id=qid,
                kind=_skipped_kind(qid),
                latency_ms=result.latency_ms,
                skip_reason=reason,
            )
            for qid in question_ids
        ]
    rows: list[JudgmentTrace] = []
    for qid in question_ids:
        answer = result.answers.get(qid)
        if answer is None:
            rows.append(
                JudgmentTrace(
                    question_id=qid,
                    kind=_skipped_kind(qid),
                    latency_ms=result.latency_ms,
                    skip_reason=skip_reason,
                )
            )
            continue
        is_noul = answer.type == "noul"
        rows.append(
            JudgmentTrace(
                question_id=qid,
                kind=answer.type,
                latency_ms=result.latency_ms,
                answer=answer.noul if is_noul else answer.choice,
                probabilities=None if is_noul else answer.probabilities,
                peakedness=None if is_noul else answer.confidence,
                model=result.model,
                input_tokens=result.input_tokens,
                consumed=qid in consumed,
                skip_reason=skip_reason,
            )
        )
    return rows


def _skipped_kind(question_id: str) -> str:
    return "noul" if question_id == "biography" else "choice"
