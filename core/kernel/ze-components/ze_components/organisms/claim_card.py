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
    tone: CardTone | None = None,
) -> ClaimCard:
    """Build a card whose tone follows its claim. `tone` overrides only where the
    design fixes it (a gate that waits on the user is cream even when stale)."""
    return ClaimCard(
        title=title,
        claim=claim,
        span=span,
        lines=(lines or [])[:3],
        readouts=(readouts or [])[:4],
        progress_done=progress_done,
        progress_total=progress_total,
        actions=actions or [],
        tone=tone or claim_tone(claim, needs_user),
    )
