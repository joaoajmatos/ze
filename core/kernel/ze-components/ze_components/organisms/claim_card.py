from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_components.claims import (
    CardAction,
    CardTone,
    ClaimPosture,
    Readout,
    claim_tone,
)


@dataclass
class ClaimCard:
    title: str
    claim: ClaimPosture
    span: Literal[4, 6, 8, 12] = 4
    lines: list[str] = field(default_factory=list)
    readouts: list[Readout] = field(default_factory=list)
    progress_done: int | None = None
    progress_total: int | None = None
    actions: list[CardAction] = field(default_factory=list)
    tone: CardTone = "default"
    type: Literal["claim_card"] = field(default="claim_card", init=False)


def claim_card(
    title: str,
    claim: ClaimPosture,
    *,
    span: Literal[4, 6, 8, 12] = 4,
    lines: list[str] | None = None,
    readouts: list[Readout] | None = None,
    progress_done: int | None = None,
    progress_total: int | None = None,
    actions: list[CardAction] | None = None,
    needs_user: bool = False,
) -> ClaimCard:
    """Build a card whose tone follows its claim; call sites never pick the tone."""
    return ClaimCard(
        title=title,
        claim=claim,
        span=span,
        lines=(lines or [])[:3],
        readouts=(readouts or [])[:4],
        progress_done=progress_done,
        progress_total=progress_total,
        actions=actions or [],
        tone=claim_tone(claim, needs_user),
    )
