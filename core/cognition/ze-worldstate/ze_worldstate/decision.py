"""The commit vocabulary: what an inflow decided to do with a text, and what came of it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ze_worldstate.types import OpenLoop

CommitKind = Literal["resolve", "create_declared", "create_suspected", "hold", "fallback"]
# What loop_judge.decide returns: the gate never declares.
GateKind = Literal["resolve", "create_suspected", "hold", "fallback"]


@dataclass(frozen=True)
class CommitDecision:
    kind: CommitKind
    reason: str
    consumed: frozenset[str] = frozenset()
    title: str | None = None  # 109 gate only
    window_days: int | None = None  # 109 gate only


CommitOutcome = Literal[
    "created", "matched", "resolved", "no_match", "no_title", "held", "dismissed", "error"
]


@dataclass(frozen=True)
class CommitResult:
    outcome: CommitOutcome
    reason: str
    loops: tuple[OpenLoop, ...] = ()
