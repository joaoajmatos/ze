from __future__ import annotations

from fastapi import APIRouter, Depends

from ze_api.api.deps import (
    get_channel_registry,
    get_user_channel_store,
    get_watermark_store,
    require_api_key,
)
from ze_api.api.v0.channels.schemas import (
    ChannelState,
    ChannelStatusItem,
    ChannelStatusResponse,
)
from ze_google.settings import get_google_settings
from ze_personal.channels.types import ChannelPollStatus, PollOutcome

router = APIRouter(
    prefix="/channels", tags=["channels"], dependencies=[Depends(require_api_key)]
)

_OUTCOME_STATE: dict[PollOutcome, ChannelState] = {
    PollOutcome.OK: "connected",
    PollOutcome.AUTH_FAILED: "needs_reauth",
    PollOutcome.FAILED: "error",
}


def _state(
    *, poll_enabled: bool, push: bool, status: ChannelPollStatus
) -> ChannelState:
    if not poll_enabled:
        return "off"
    if push or status.last_outcome is None:
        return "unknown"
    return _OUTCOME_STATE[status.last_outcome]


@router.get(
    "/status",
    response_model=ChannelStatusResponse,
    operation_id="listChannelStatus",
    summary="List channel connection status",
    description="Report each inbound channel's connection state and last sync. "
    "Push channels report unknown. No tokens or secrets.",
)
async def list_channel_status(
    user_channels=Depends(get_user_channel_store),
    watermarks=Depends(get_watermark_store),
    registry=Depends(get_channel_registry),
) -> ChannelStatusResponse:
    rows = await user_channels.list_all()
    inbound = {c.channel_id: c for c in registry.inbound_channels()}
    known = {r.channel_id for r in rows}
    statuses = await watermarks.get_status_many(
        [*known, *(c for c in inbound if c not in known)]
    )
    empty = ChannelPollStatus(watermark=None, last_outcome=None, last_outcome_at=None)

    def item(
        channel_id: str,
        *,
        channel_type: str,
        handle: str | None,
        display_name: str | None,
        poll_enabled: bool,
    ) -> ChannelStatusItem:
        status = statuses.get(channel_id, empty)
        live = inbound.get(channel_id)
        push = bool(live and live.supports_push)
        return ChannelStatusItem(
            channel_id=channel_id,
            channel_type=channel_type,
            handle=handle,
            display_name=display_name,
            state=_state(poll_enabled=poll_enabled, push=push, status=status),
            last_sync_at=status.watermark
            if status.last_outcome is PollOutcome.OK
            else None,
            push=push,
        )

    items = [
        item(
            r.channel_id,
            channel_type=r.channel_type,
            handle=r.handle,
            display_name=r.display_name,
            poll_enabled=r.poll_enabled,
        )
        for r in rows
    ]
    items += [
        item(
            channel_id,
            channel_type=channel.channel_type.value,
            handle=None,
            display_name=None,
            poll_enabled=True,
        )
        for channel_id, channel in inbound.items()
        if channel_id not in known
    ]
    google = get_google_settings()
    return ChannelStatusResponse(
        google_configured=bool(
            google.google_client_id
            and google.google_client_secret
            and google.google_refresh_token
        ),
        channels=items,
    )
