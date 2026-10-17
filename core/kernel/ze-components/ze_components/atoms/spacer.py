from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_components.claims import ClaimPosture


@dataclass
class Spacer:
    size: Literal["sm", "md", "lg"] = "md"
    claim: ClaimPosture | None = None
    type: Literal["spacer"] = field(default="spacer", init=False)


def spacer(size: str = "md") -> Spacer:
    return Spacer(size=size)  # type: ignore[arg-type]
