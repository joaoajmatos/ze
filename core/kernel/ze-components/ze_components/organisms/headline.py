from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_components.claims import ClaimPosture, headline_text


@dataclass
class Headline:
    text: str
    claim: ClaimPosture | None = None
    type: Literal["headline"] = field(default="headline", init=False)


def headline(text: str) -> Headline:
    return Headline(text=headline_text(text))
