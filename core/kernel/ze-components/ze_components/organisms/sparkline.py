from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_agents.errors import InvalidComponentError

from ze_components.claims import ClaimPosture

SPARKLINE_MAX_POINTS = 60


@dataclass
class Sparkline:
    label: str
    points: list[float] = field(
        metadata={"json_schema": {"maxItems": SPARKLINE_MAX_POINTS}}
    )
    value: str | None = None
    claim: ClaimPosture | None = None
    type: Literal["sparkline"] = field(default="sparkline", init=False)

    def __post_init__(self) -> None:
        if len(self.points) > SPARKLINE_MAX_POINTS:
            raise InvalidComponentError(
                f"sparkline holds at most {SPARKLINE_MAX_POINTS} points, got {len(self.points)}"
            )


def sparkline(
    label: str, points: list[float], *, value: str | None = None
) -> Sparkline:
    return Sparkline(label=label, points=points, value=value)
