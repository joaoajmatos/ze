from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_agents.errors import InvalidComponentError

ASK_TEXT_MAX = 500
ComposeKind = Literal["slipping", "decisions", "topic"]
ArgValue = str | int | float | bool


@dataclass
class AskAction:
    """Send `text` as a chat message on the selected thread."""

    text: str = field(
        metadata={"json_schema": {"minLength": 1, "maxLength": ASK_TEXT_MAX}}
    )
    kind: Literal["ask"] = field(default="ask", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not 1 <= len(self.text) <= ASK_TEXT_MAX:
            raise InvalidComponentError(
                f"ask action text must be 1 to {ASK_TEXT_MAX} characters"
            )


@dataclass
class ToolAction:
    """Run one of `owner`'s write tools that opted in with `ui_action=True`."""

    owner: str
    tool: str
    args: dict[str, ArgValue]
    kind: Literal["tool"] = field(default="tool", init=False)

    def __post_init__(self) -> None:
        for key, value in self.args.items():
            if not isinstance(value, (str, int, float, bool)):
                raise InvalidComponentError(
                    f"tool action arg {key!r} must be a scalar, got {type(value).__name__}"
                )


@dataclass
class NavigateAction:
    """Go to a place route, optionally with a `#section`."""

    route: str = field(metadata={"json_schema": {"pattern": "^/"}})
    kind: Literal["navigate"] = field(default="navigate", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.route, str) or not self.route.startswith("/"):
            raise InvalidComponentError("navigate route must start with '/'")


@dataclass
class ComposeAction:
    """Ask for a composed answer (phase 184), with the preset context."""

    compose: ComposeKind
    topic: str | None = None
    kind: Literal["compose"] = field(default="compose", init=False)


PrimitiveAction = AskAction | ToolAction | NavigateAction | ComposeAction
ACTION_TYPES: list[type] = [AskAction, ToolAction, NavigateAction, ComposeAction]


def require_action(action: object) -> None:
    if not isinstance(action, (AskAction, ToolAction, NavigateAction, ComposeAction)):
        raise InvalidComponentError(
            f"action must be a typed PrimitiveAction, got {type(action).__name__}"
        )
