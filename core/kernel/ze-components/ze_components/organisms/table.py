from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_agents.errors import InvalidComponentError

from ze_components.actions import PrimitiveAction, require_action
from ze_components.claims import ClaimPosture


@dataclass
class RowAction:
    """A button on every row. A tool action's args may use `"{key}"`, which the host fills from the row's key."""

    label: str
    action: PrimitiveAction

    def __post_init__(self) -> None:
        require_action(self.action)


@dataclass
class Table:
    headers: list[str]
    rows: list[list[str]]
    title: str | None = None
    caption: str | None = None
    keys: list[str] | None = field(
        default=None, metadata={"json_schema": {"uniqueItems": True}}
    )
    row_actions: list[RowAction] | None = None
    claim: ClaimPosture | None = None
    type: Literal["table"] = field(default="table", init=False)

    def __post_init__(self) -> None:
        if self.keys is not None and len(self.keys) != len(self.rows):
            raise InvalidComponentError(
                f"table has {len(self.rows)} rows but {len(self.keys)} keys"
            )
        if self.keys is not None and len(set(self.keys)) != len(self.keys):
            raise InvalidComponentError("table keys must be unique")
        if self.row_actions and self.keys is None:
            raise InvalidComponentError("table row actions need keys")


def table(
    headers: list[str],
    rows: list[list[str]],
    *,
    title: str | None = None,
    caption: str | None = None,
    keys: list[str] | None = None,
    row_actions: list[RowAction] | None = None,
) -> Table:
    return Table(
        headers=headers,
        rows=rows,
        title=title,
        caption=caption,
        keys=keys,
        row_actions=row_actions,
    )
