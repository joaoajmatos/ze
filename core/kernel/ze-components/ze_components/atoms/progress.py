from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_components.claims import ClaimPosture


@dataclass
class ProgressBar:
    value: float  # 0.0 – 1.0
    label: str | None = None
    claim: ClaimPosture | None = None
    type: Literal["progress"] = field(default="progress", init=False)


def progress(value: float, label: str | None = None) -> ProgressBar:
    return ProgressBar(value=value, label=label)
