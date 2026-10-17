from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_components.claims import ClaimPosture


@dataclass
class Divider:
    claim: ClaimPosture | None = None
    type: Literal["divider"] = field(default="divider", init=False)


def divider() -> Divider:
    return Divider()
