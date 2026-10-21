from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_components.actions import PrimitiveAction, require_action
from ze_components.claims import ClaimPosture


@dataclass
class FacetFact:
    text: str
    claim: ClaimPosture
    source: str | None = None
    at: str | None = None


@dataclass
class EntityFacet:
    title: str
    facts: list[FacetFact]
    more: PrimitiveAction | None = None
    claim: ClaimPosture | None = None
    type: Literal["entity_facet"] = field(default="entity_facet", init=False)

    def __post_init__(self) -> None:
        if self.more is not None:
            require_action(self.more)


def entity_facet(
    title: str, facts: list[FacetFact], *, more: PrimitiveAction | None = None
) -> EntityFacet:
    return EntityFacet(title=title, facts=facts, more=more)
