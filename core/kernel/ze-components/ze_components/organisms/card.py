from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_components.atoms.button import Button
from ze_components.claims import ClaimPosture


@dataclass
class Card:
    title: str
    children: list
    actions: list[Button] = field(default_factory=list)
    body: str | None = None
    claim: ClaimPosture | None = None
    type: Literal["card"] = field(default="card", init=False)


def card_with_actions(
    title: str,
    children: list,
    *,
    body: str | None = None,
    actions: list[Button] | None = None,
) -> Card:
    return Card(title=title, children=children, actions=actions or [], body=body)
