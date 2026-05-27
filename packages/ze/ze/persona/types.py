from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PersonaState:
    profile: str
    dials: dict[str, float] = field(default_factory=dict)
    updated_at: datetime | None = None
