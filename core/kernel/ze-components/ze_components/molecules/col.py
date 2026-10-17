from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_components.claims import ClaimPosture


@dataclass
class Col:
    children: list
    gap: Literal["none", "sm", "md", "lg"] = "sm"
    variant: Literal["default", "card", "section"] = "default"
    claim: ClaimPosture | None = None
    type: Literal["col"] = field(default="col", init=False)


def col(children: list, *, gap: str = "sm") -> Col:
    return Col(children=children, gap=gap)  # type: ignore[arg-type]


def card(children: list, *, gap: str = "sm") -> Col:
    return Col(children=children, gap=gap, variant="card")  # type: ignore[arg-type]


def section(children: list, *, gap: str = "sm") -> Col:
    return Col(children=children, gap=gap, variant="section")  # type: ignore[arg-type]
