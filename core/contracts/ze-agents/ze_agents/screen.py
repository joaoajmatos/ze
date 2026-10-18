"""Screen context contract — what the user can see, as typed refs Ze resolves from its own records.

The client sends refs (kind, id, display hints). It never sends facts: resolvers load the
record by id and set posture from it, so a client label can mislead nothing but its own
display. `ScreenContext.from_wire` never raises; bad input becomes warnings.
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from ze_agents.claims import ClaimKind
from ze_logging import get_logger

log = get_logger(__name__)

PLACES = frozenset({"world", "ask", "doing", "mind", "governance", "plugin"})
COMPOSE_PRESETS = frozenset({"slipping", "decisions", "topic"})

MAX_SUBJECT = 3
MAX_SELECTION = 20
MAX_VISIBLE = 30
MAX_CANVAS = 12
MAX_PLACED = 50
MAX_ID = 64
MAX_LABEL = 120
MAX_COMPONENT = 40
MAX_ROUTE = 200
MAX_FOCUSED = 80
MAX_TOPIC = 120
MAX_PATH = 512
MAX_SUMMARY = 240
MAX_WARNINGS = 20


class ScreenOrigin(StrEnum):
    ASK_BAR = "ask_bar"
    CHAT_ABOUT = "chat_about"
    PRESET = "preset"


class ScreenStatus(StrEnum):
    OK = "ok"
    MISSING = "missing"
    CHANGED = "changed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CUT = "cut"


@dataclass(frozen=True)
class ScreenRef:
    kind: str
    id: str
    label: str | None = None
    component: str | None = None
    parent_id: str | None = None
    as_of: datetime | None = None


@dataclass(frozen=True)
class CanvasRef:
    index: int
    type: str
    ref: ScreenRef | None = None


@dataclass(frozen=True)
class WorkspacePlaced:
    path: str
    size: int | None = None


@dataclass(frozen=True)
class ScreenContext:
    place: str | None = None
    route: str | None = None
    origin: ScreenOrigin = ScreenOrigin.ASK_BAR
    subject: tuple[ScreenRef, ...] = ()
    selection: tuple[ScreenRef, ...] = ()
    visible: tuple[ScreenRef, ...] = ()
    focused_module: str | None = None
    canvas: tuple[CanvasRef, ...] = ()
    captured_at: datetime | None = None
    compose: str | None = None
    topic: str | None = None
    workspace_placed: tuple[WorkspacePlaced, ...] = ()

    @property
    def is_empty(self) -> bool:
        return self == ScreenContext()

    @classmethod
    def from_wire(
        cls, wire: Any, *, received_at: datetime | None = None
    ) -> tuple[ScreenContext, list[str]]:
        """Parse a client `context` dict. Invalid values are dropped and returned as warnings."""
        received = received_at or datetime.now(UTC)
        warnings: list[str] = []
        if wire is None:
            return cls(), warnings
        if not isinstance(wire, dict):
            return cls(), ["context is not an object"]
        known = {
            "place",
            "route",
            "origin",
            "subject",
            "selection",
            "visible",
            "focused_module",
            "canvas",
            "captured_at",
            "compose",
            "topic",
            "workspace_placed",
            "voice",
        }
        for key in wire:
            if key not in known:
                warnings.append(f"unknown key: {_short(key)}")

        place = wire.get("place")
        if place is not None and place not in PLACES:
            warnings.append(f"place: unknown value {_short(place)}")
            place = None

        origin = ScreenOrigin.ASK_BAR
        raw_origin = wire.get("origin")
        if raw_origin is not None:
            try:
                origin = ScreenOrigin(raw_origin)
            except ValueError:
                warnings.append(f"origin: unknown value {_short(raw_origin)}")

        compose = wire.get("compose")
        if compose is not None and compose not in COMPOSE_PRESETS:
            warnings.append(f"compose: unknown value {_short(compose)}")
            compose = None

        ctx = cls(
            place=place,
            route=_opt_text(wire.get("route"), MAX_ROUTE, "route", warnings),
            origin=origin,
            subject=_refs(wire.get("subject"), MAX_SUBJECT, "subject", warnings),
            selection=_refs(
                wire.get("selection"), MAX_SELECTION, "selection", warnings
            ),
            visible=_refs(wire.get("visible"), MAX_VISIBLE, "visible", warnings),
            focused_module=_opt_text(
                wire.get("focused_module"), MAX_FOCUSED, "focused_module", warnings
            ),
            canvas=_canvas(wire.get("canvas"), warnings),
            captured_at=_captured_at(wire.get("captured_at"), received, warnings),
            compose=compose,
            topic=_topic(wire.get("topic"), warnings),
            workspace_placed=_placed(wire.get("workspace_placed"), warnings),
        )
        return ctx, warnings[:MAX_WARNINGS]

    def to_wire(self) -> dict[str, Any]:
        """JSON-safe form for storage; `from_wire` reads it back."""
        return {
            "place": self.place,
            "route": self.route,
            "origin": self.origin.value,
            "subject": [_ref_wire(r) for r in self.subject],
            "selection": [_ref_wire(r) for r in self.selection],
            "visible": [_ref_wire(r) for r in self.visible],
            "focused_module": self.focused_module,
            "canvas": [
                {
                    "index": c.index,
                    "type": c.type,
                    "ref": _ref_wire(c.ref) if c.ref else None,
                }
                for c in self.canvas
            ],
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "compose": self.compose,
            "topic": self.topic,
            "workspace_placed": [
                {"path": p.path, "size": p.size} for p in self.workspace_placed
            ]
            or None,
        }


@dataclass(frozen=True)
class ScreenPosture:
    """Epistemic standing of the record a line describes, read from the record by code."""

    kind: ClaimKind | None = None
    source: str | None = None
    confidence: float | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class ScreenLine:
    ref: ScreenRef
    label: str
    summary: str = ""
    posture: ScreenPosture | None = None
    status: ScreenStatus = ScreenStatus.OK
    target: ScreenRef | None = field(
        default=None
    )  # notification: the one-hop target to resolve


@dataclass(frozen=True)
class ResolveContext:
    now: datetime
    captured_at: datetime | None = None
    origin: ScreenOrigin = ScreenOrigin.ASK_BAR
    placed: tuple[WorkspacePlaced, ...] = ()  # files the user placed this turn, for `workspace_placed`


@runtime_checkable
class ScreenResolver(Protocol):
    """Loads records by id for the kinds it owns. Never raises; reports `status` per line."""

    kinds: frozenset[str]

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]: ...


_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f  ]+")
_SPACE = re.compile(r"\s+")
_BINDING = re.compile(r"""(?i)["“”'‘’]?\b(this|it|that|these|those)\b["“”'‘’]?\s*=""")
_LEADING = "[\"'“”‘’ "


def sanitize_text(value: object, cap: int) -> str:
    """One inert line: control characters collapsed, brackets and binding patterns defused, capped."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = _CONTROL.sub(" ", text)
    text = text.replace("[", "(").replace("]", ")")
    text = _BINDING.sub(r"\1 -", text)
    text = _SPACE.sub(" ", text).strip().lstrip(_LEADING)
    return text[:cap].rstrip()


def time_ago(then: datetime, now: datetime) -> str:
    seconds = max(0, int((now - then).total_seconds()))
    if seconds < 3600:
        return f"{max(1, seconds // 60)} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    return f"{seconds // 86400} d ago"


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def parse_uuid(value: str | None) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


async def resolve_each(
    refs: list[ScreenRef],
    load: Callable[[ScreenRef], Awaitable[ScreenLine | None]],
) -> list[ScreenLine]:
    """Resolver helper: `load` returns a line, or None when the record is gone; an error becomes `failed`.

    Never raises and never puts error text in a line, so a resolver built on it cannot leak a store error.
    """

    async def one(ref: ScreenRef) -> ScreenLine:
        label = sanitize_text(ref.label or ref.id, MAX_LABEL)
        try:
            line = await load(ref)
        except Exception as exc:
            log.warning("screen_resolver_ref_failed", kind=ref.kind, error=type(exc).__name__)
            return ScreenLine(ref=ref, label=label, status=ScreenStatus.FAILED)
        if line is None:
            return ScreenLine(ref=ref, label=label, status=ScreenStatus.MISSING)
        return line

    return list(await asyncio.gather(*(one(r) for r in refs)))


def _short(value: object) -> str:
    return sanitize_text(value, 40)


def _opt_text(value: Any, cap: int, name: str, warnings: list[str]) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        warnings.append(f"{name}: not a string")
        return None
    return value[:cap]


def _topic(value: Any, warnings: list[str]) -> str | None:
    # A topic over the cap is dropped, not cut: a cut topic would compose a different answer.
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > MAX_TOPIC:
        warnings.append(f"topic: not a string of at most {MAX_TOPIC} characters")
        return None
    return value


def _id_field(
    value: Any, name: str, warnings: list[str], *, required: bool
) -> str | None:
    if value is None:
        if required:
            warnings.append(f"ref {name}: missing")
        return None
    if not isinstance(value, str) or not value:
        warnings.append(f"ref {name}: not a non-empty string")
        return None
    if len(value) > MAX_ID:
        warnings.append(f"ref {name}: longer than {MAX_ID}")
        return None
    return value


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _ref(raw: Any, slot: str, warnings: list[str]) -> ScreenRef | None:
    if not isinstance(raw, dict):
        warnings.append(f"{slot}: ref is not an object")
        return None
    kind = _id_field(raw.get("kind"), "kind", warnings, required=True)
    id_ = _id_field(raw.get("id"), "id", warnings, required=True)
    parent = _id_field(raw.get("parent_id"), "parent_id", warnings, required=False)
    if raw.get("parent_id") is not None and parent is None:
        return None
    if kind is None or id_ is None:
        return None
    as_of = None
    if raw.get("as_of") is not None:
        as_of = _parse_time(raw["as_of"])
        if as_of is None:
            warnings.append(f"{slot}: as_of is not an ISO time")
    return ScreenRef(
        kind=kind,
        id=id_,
        label=_opt_text(raw.get("label"), MAX_LABEL, "label", warnings),
        component=_opt_text(raw.get("component"), MAX_COMPONENT, "component", warnings),
        parent_id=parent,
        as_of=as_of,
    )


def _refs(raw: Any, cap: int, slot: str, warnings: list[str]) -> tuple[ScreenRef, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        warnings.append(f"{slot}: not a list")
        return ()
    if len(raw) > cap:
        warnings.append(f"{slot}: {len(raw) - cap} refs over the cap of {cap} dropped")
    out = [r for item in raw[:cap] if (r := _ref(item, slot, warnings)) is not None]
    return tuple(out)


def _canvas(raw: Any, warnings: list[str]) -> tuple[CanvasRef, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        warnings.append("canvas: not a list")
        return ()
    if len(raw) > MAX_CANVAS:
        warnings.append(f"canvas: {len(raw) - MAX_CANVAS} entries over the cap dropped")
    out: list[CanvasRef] = []
    for item in raw[:MAX_CANVAS]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("index"), int)
            or isinstance(item.get("index"), bool)
            or not isinstance(item.get("type"), str)
        ):
            warnings.append("canvas: malformed entry")
            continue
        ref = (
            _ref(item["ref"], "canvas", warnings)
            if item.get("ref") is not None
            else None
        )
        out.append(
            CanvasRef(index=item["index"], type=item["type"][:MAX_COMPONENT], ref=ref)
        )
    return tuple(out)


def _placed(raw: Any, warnings: list[str]) -> tuple[WorkspacePlaced, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        warnings.append("workspace_placed: not a list")
        return ()
    out: list[WorkspacePlaced] = []
    for item in raw[:MAX_PLACED]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            warnings.append("workspace_placed: malformed entry")
            continue
        size = item.get("size")
        out.append(
            WorkspacePlaced(
                path=item["path"][:MAX_PATH],
                size=size
                if isinstance(size, int) and not isinstance(size, bool)
                else None,
            )
        )
    return tuple(out)


def _captured_at(raw: Any, received: datetime, warnings: list[str]) -> datetime | None:
    if raw is None:
        return None
    parsed = _parse_time(raw)
    if parsed is None:
        warnings.append("captured_at: not an ISO time")
        return None
    if parsed > received:
        log.info(
            "screen_context_clock_skew",
            skew_seconds=(parsed - received).total_seconds(),
        )
        return received
    return parsed


def _ref_wire(ref: ScreenRef | None) -> dict[str, Any] | None:
    if ref is None:
        return None
    return {
        "kind": ref.kind,
        "id": ref.id,
        "label": ref.label,
        "component": ref.component,
        "parent_id": ref.parent_id,
        "as_of": ref.as_of.isoformat() if ref.as_of else None,
    }
