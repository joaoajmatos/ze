from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_components.actions import PrimitiveAction, require_action
from ze_components.claims import ClaimPosture


@dataclass
class ClaimItem:
    text: str
    claim: ClaimPosture
    action: PrimitiveAction | None = None

    def __post_init__(self) -> None:
        if self.action is not None:
            require_action(self.action)


@dataclass
class ClaimList:
    items: list[ClaimItem]
    title: str | None = None
    claim: ClaimPosture | None = None
    type: Literal["claim_list"] = field(default="claim_list", init=False)


def claim_list(items: list[ClaimItem], *, title: str | None = None) -> ClaimList:
    return ClaimList(items=items, title=title)
