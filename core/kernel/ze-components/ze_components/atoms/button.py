from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_components.actions import PrimitiveAction, require_action
from ze_components.claims import ClaimPosture


@dataclass
class Button:
    label: str
    action: PrimitiveAction
    style: Literal["primary", "secondary", "danger"] = "secondary"
    claim: ClaimPosture | None = None
    type: Literal["button"] = field(default="button", init=False)

    def __post_init__(self) -> None:
        require_action(self.action)


def button(label: str, action: PrimitiveAction, style: str = "secondary") -> Button:
    return Button(label, action, style=style)  # type: ignore[arg-type]


def primary(label: str, action: PrimitiveAction) -> Button:
    return Button(label, action, style="primary")


def secondary(label: str, action: PrimitiveAction) -> Button:
    return Button(label, action, style="secondary")


def danger(label: str, action: PrimitiveAction) -> Button:
    return Button(label, action, style="danger")
