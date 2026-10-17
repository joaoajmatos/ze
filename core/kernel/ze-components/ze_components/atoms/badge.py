from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_components.claims import ClaimPosture


@dataclass
class Badge:
    label: str
    color: Literal["default", "success", "warning", "error", "info"] = "default"
    claim: ClaimPosture | None = None
    type: Literal["badge"] = field(default="badge", init=False)


def badge(label: str, color: str = "default") -> Badge:
    return Badge(label, color=color)  # type: ignore[arg-type]


def success(label: str) -> Badge:
    return Badge(label, color="success")


def warning(label: str) -> Badge:
    return Badge(label, color="warning")


def error(label: str) -> Badge:
    return Badge(label, color="error")


def info(label: str) -> Badge:
    return Badge(label, color="info")
