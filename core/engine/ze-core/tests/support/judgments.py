"""Builders for ``Judgment`` records in node tests."""

from __future__ import annotations

from collections.abc import Mapping

from ze_agents.judgment import Judgment, SurfaceBar
from ze_agents.system_one import SystemOneResult


def make_judgment(
    surface: str,
    result: SystemOneResult,
    question_kinds: Mapping[str, str],
    *,
    consumed: frozenset[str] = frozenset(),
    skip_reason: str | None = None,
    bars: Mapping[str, SurfaceBar | None] | None = None,
) -> Judgment:
    bars = bars or {}
    return Judgment(
        surface=surface,
        result=result,
        question_kinds=dict(question_kinds),
        consumed=consumed,
        skip_reason=skip_reason,
        bars={qid: bars.get(qid) for qid in question_kinds},
    )
