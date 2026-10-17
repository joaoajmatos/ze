from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_components.claims import ClaimPosture


@dataclass
class Button:
    label: str
    action: str
    style: Literal["primary", "secondary", "danger"] = "secondary"
    claim: ClaimPosture | None = None
    type: Literal["button"] = field(default="button", init=False)


def button(label: str, action: str, style: str = "secondary") -> Button:
    return Button(label, action, style=style)  # type: ignore[arg-type]


def primary(label: str, action: str) -> Button:
    return Button(label, action, style="primary")


def secondary(label: str, action: str) -> Button:
    return Button(label, action, style="secondary")


def danger(label: str, action: str) -> Button:
    return Button(label, action, style="danger")
