"""Screen context contract for plugins: resolver protocol, refs, lines and sanitiser."""

from ze_agents.screen import (
    CanvasRef,
    ResolveContext,
    ScreenContext,
    ScreenLine,
    ScreenOrigin,
    ScreenPosture,
    ScreenRef,
    ScreenResolver,
    ScreenStatus,
    WorkspacePlaced,
    as_utc,
    parse_uuid,
    resolve_each,
    sanitize_text,
    time_ago,
)

__all__ = [
    "CanvasRef",
    "ResolveContext",
    "ScreenContext",
    "ScreenLine",
    "ScreenOrigin",
    "ScreenPosture",
    "ScreenRef",
    "ScreenResolver",
    "ScreenStatus",
    "WorkspacePlaced",
    "as_utc",
    "parse_uuid",
    "resolve_each",
    "sanitize_text",
    "time_ago",
]
