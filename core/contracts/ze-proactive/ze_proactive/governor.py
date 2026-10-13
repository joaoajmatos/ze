from __future__ import annotations

from typing import Literal

from ze_proactive.types import PushKind

Decision = Literal["deliver", "hold", "suppress"]


def decide(kind: PushKind, *, quiet_now: bool, budget_won: bool | None) -> Decision:
    if kind.push_class == "requested":
        return "deliver"
    if quiet_now:
        return "hold"
    if kind.push_class == "accountability":
        return "deliver"
    return "deliver" if budget_won else "suppress"
