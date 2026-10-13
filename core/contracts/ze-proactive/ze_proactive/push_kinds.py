from __future__ import annotations

from ze_proactive.errors import PushPolicyError
from ze_proactive.types import PushKind

_registry: dict[str, PushKind] = {}


def register(kind: PushKind) -> None:
    existing = _registry.get(kind.event_type)
    if existing is None:
        _registry[kind.event_type] = kind
        return
    if existing != kind:
        raise PushPolicyError(
            f"push kind {kind.event_type!r} already registered as "
            f"{existing.push_class}/{existing.urgency}/{existing.source}"
        )


def registered_push_kinds() -> dict[str, PushKind]:
    return dict(_registry)


QUIET_HOURS_SUMMARY = PushKind(
    "quiet_hours_summary", "accountability", "normal", "proactive"
)
