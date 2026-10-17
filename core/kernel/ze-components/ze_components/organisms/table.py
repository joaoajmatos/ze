from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_components.claims import ClaimPosture


@dataclass
class Table:
    headers: list[str]
    rows: list[list[str]]
    title: str | None = None
    caption: str | None = None
    claim: ClaimPosture | None = None
    type: Literal["table"] = field(default="table", init=False)


def table(
    headers: list[str],
    rows: list[list[str]],
    *,
    title: str | None = None,
    caption: str | None = None,
) -> Table:
    return Table(headers=headers, rows=rows, title=title, caption=caption)
