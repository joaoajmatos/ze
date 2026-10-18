from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ze_agents.errors import InvalidComponentError
from ze_agents.screen import COMPOSE_PRESETS, MAX_TOPIC

ASK_TEXT_MAX = 500
NAME_MAX = 64
ARGS_MAX = 12
ARG_VALUE_MAX = 200
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

    owner: str = field(
        metadata={"json_schema": {"minLength": 1, "maxLength": NAME_MAX}}
    )
    tool: str = field(metadata={"json_schema": {"minLength": 1, "maxLength": NAME_MAX}})
    args: dict[str, ArgValue] = field(
        metadata={
            "json_schema": {
                "maxProperties": ARGS_MAX,
                "propertyNames": {"maxLength": NAME_MAX},
                "additionalProperties": {
                    "type": ["string", "number", "boolean"],
                    "maxLength": ARG_VALUE_MAX,
                },
            }
        }
    )
    kind: Literal["tool"] = field(default="tool", init=False)

    def __post_init__(self) -> None:
        for name in (self.owner, self.tool):
            if not isinstance(name, str) or not 1 <= len(name) <= NAME_MAX:
                raise InvalidComponentError(
                    f"tool action owner and tool must be 1 to {NAME_MAX} characters"
                )
        if len(self.args) > ARGS_MAX:
            raise InvalidComponentError(f"tool action takes at most {ARGS_MAX} args")
        for key, value in self.args.items():
            if len(key) > NAME_MAX:
                raise InvalidComponentError(
                    f"tool action arg name {key[:20]!r}... is too long"
                )
            if isinstance(value, str) and len(value) > ARG_VALUE_MAX:
                raise InvalidComponentError(
                    f"tool action arg {key!r} is over {ARG_VALUE_MAX} characters"
                )
            if not isinstance(value, (str, int, float, bool)):
                raise InvalidComponentError(
                    f"tool action arg {key!r} must be a scalar, got {type(value).__name__}"
                )


@dataclass
class NavigateAction:
    """Go to a place route, optionally with a `#section`."""

    route: str = field(
        metadata={"json_schema": {"pattern": "^/(?!/)(?![\\s\\S]*\\.\\.)"}}
    )
    kind: Literal["navigate"] = field(default="navigate", init=False)

    def __post_init__(self) -> None:
        route = self.route
        if (
            not isinstance(route, str)
            or not route.startswith("/")
            or route.startswith("//")
            or ".." in route
        ):
            raise InvalidComponentError(
                "navigate route must be a place route: start with one '/', no '..'"
            )


@dataclass
class ComposeAction:
    """Ask for a composed answer (phase 184), with the preset context."""

    compose: ComposeKind
    topic: str | None = field(
        default=None, metadata={"json_schema": {"maxLength": MAX_TOPIC}}
    )
    kind: Literal["compose"] = field(default="compose", init=False)

    def __post_init__(self) -> None:
        if self.compose not in COMPOSE_PRESETS:
            raise InvalidComponentError(f"unknown compose preset {self.compose!r}")
        if self.topic is not None and len(self.topic) > MAX_TOPIC:
            raise InvalidComponentError(f"compose topic is over {MAX_TOPIC} characters")


PrimitiveAction = AskAction | ToolAction | NavigateAction | ComposeAction
ACTION_TYPES: list[type] = [AskAction, ToolAction, NavigateAction, ComposeAction]


def require_action(action: object) -> None:
    if not isinstance(action, (AskAction, ToolAction, NavigateAction, ComposeAction)):
        raise InvalidComponentError(
            f"action must be a typed PrimitiveAction, got {type(action).__name__}"
        )
