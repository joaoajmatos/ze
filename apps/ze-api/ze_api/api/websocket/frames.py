"""Builders for the `confirm_request` frame (Phase 181, contracts/ws-confirmation.md)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from ze_agents.park import WriteConfirmation

CONFIRM_ACTIONS: list[dict[str, str]] = [
    {"label": "Approve all", "value": "approve", "style": "primary"},
    {"label": "Deny all", "value": "deny", "style": "secondary"},
]

_TITLES = {
    "write": "Ze needs your OK",
    "budget": "Ze needs your OK to keep going",
    "held": "Ze is waiting for your OK",
}


def confirmation_payload(confirmation: WriteConfirmation) -> dict[str, Any]:
    """What `pending_confirmations.actions` stores: enough to rebuild the frame."""
    return {
        "kind": confirmation.kind,
        "round": confirmation.round,
        "items": [asdict(item) for item in confirmation.items],
    }


def confirm_title(kind: str) -> str:
    return _TITLES.get(kind, _TITLES["write"])


def build_confirm_frame(
    *,
    request_id: str,
    thread_id: str | None,
    kind: str,
    round_: int,
    items: list[dict[str, Any]],
    expires_at: datetime | None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": "confirm_request",
        "id": request_id,
        "thread_id": thread_id,
        "kind": kind,
        "round": round_,
        "title": confirm_title(kind),
        "items": items,
        "source": source,
        "expires_at": expires_at.isoformat() if expires_at is not None else None,
        "actions": [dict(a) for a in CONFIRM_ACTIONS],
    }


def frame_from_pending(pending: dict[str, Any]) -> dict[str, Any]:
    """Rebuild a frame from a `pending_confirmations` row (replay on connect)."""
    payload = pending.get("actions") or {}
    if not isinstance(payload, dict):
        payload = {}
    return build_confirm_frame(
        request_id=pending["request_id"],
        thread_id=pending.get("thread_id"),
        kind=str(payload.get("kind") or "write"),
        round_=int(payload.get("round") or 1),
        items=list(payload.get("items") or []),
        expires_at=pending.get("expires_at"),
        source=payload.get("source"),
    )
