from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_agents.errors import InvalidComponentError

from ze_components.claims import ClaimPosture

STAT_ROW_MAX = 6


@dataclass
class Stat:
    label: str
    value: str
    delta: str | None = None
    direction: Literal["up", "down", "flat"] | None = None


@dataclass
class StatRow:
    items: list[Stat] = field(
        metadata={"json_schema": {"minItems": 1, "maxItems": STAT_ROW_MAX}}
    )
    claim: ClaimPosture | None = None
    type: Literal["stat_row"] = field(default="stat_row", init=False)

    def __post_init__(self) -> None:
        if not 1 <= len(self.items) <= STAT_ROW_MAX:
            raise InvalidComponentError(
                f"stat row needs 1 to {STAT_ROW_MAX} items, got {len(self.items)}"
            )


def stat_row(items: list[Stat]) -> StatRow:
    return StatRow(items=items)
