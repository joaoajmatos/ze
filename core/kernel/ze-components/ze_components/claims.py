from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

ClaimKindName = Literal[
    "identity",
    "fact",
    "inference",
    "suspicion",
    "priority",
    "action_record",
    "feedback_record",
]
ClaimSubject = Literal[
    "loop", "goal", "workflow", "hypothesis", "person", "held_write", "fact"
]
CardTone = Literal["default", "cream", "hot", "dotted"]
CardIntent = Literal[
    "confirm_loop",
    "drop_loop",
    "approve_held_write",
    "deny_held_write",
    "approve_gate",
    "open",
]

HEADLINE_MAX = 40
_NOT_GLYPH = re.compile(r"[^A-Z0-9·:\- ]")


@dataclass(kw_only=True)
class ClaimPosture:
    kind: ClaimKindName | None = None
    subject: ClaimSubject
    ref_id: str
    confidence: float | None = None
    confidence_from: float | None = None
    source: str | None = None
    as_of: str | None = None
    state: str | None = None
    slipped: bool = False


@dataclass
class Readout:
    label: str
    value: str
    tone: Literal["default", "live", "hot"] = "default"


@dataclass
class CardAction:
    label: str
    intent: CardIntent
    ref_id: str


@dataclass
class TimelineEntry:
    title: str
    claim: ClaimPosture
    due_at: str | None = None


def headline_text(text: str) -> str:
    """Uppercase text reduced to the DotMatrix glyph set, at most 40 characters."""
    folded = unicodedata.normalize("NFKD", text.upper())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    cleaned = _NOT_GLYPH.sub("", folded)
    return " ".join(cleaned.split())[:HEADLINE_MAX].rstrip()


def claim_tone(claim: ClaimPosture, needs_user: bool = False) -> CardTone:
    if claim.slipped:
        return "hot"
    if needs_user:
        return "cream"
    if claim.kind in ("suspicion", "inference"):
        return "dotted"
    return "default"
