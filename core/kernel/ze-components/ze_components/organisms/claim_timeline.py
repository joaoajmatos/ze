from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_components.claims import ClaimPosture, TimelineEntry


@dataclass
class ClaimTimeline:
    title: str
    entries: list[TimelineEntry]
    days_before: int = 7
    days_after: int = 7
    span: Literal[4, 6, 8, 12] = 12
    claim: ClaimPosture | None = None
    type: Literal["claim_timeline"] = field(default="claim_timeline", init=False)


def claim_timeline(
    title: str,
    entries: list[TimelineEntry],
    *,
    days_before: int = 7,
    days_after: int = 7,
    span: Literal[4, 6, 8, 12] = 12,
) -> ClaimTimeline:
    ordered = sorted(entries, key=lambda e: (e.due_at is None, e.due_at or ""))
    return ClaimTimeline(
        title=title,
        entries=ordered,
        days_before=days_before,
        days_after=days_after,
        span=span,
    )
