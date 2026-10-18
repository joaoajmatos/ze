from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ze_api.api.deps import require_api_key
from ze_api.api.v0.channels.schemas import ChannelStatusResponse

router = APIRouter(
    prefix="/channels", tags=["channels"], dependencies=[Depends(require_api_key)]
)


@router.get(
    "/status",
    response_model=ChannelStatusResponse,
    operation_id="listChannelStatus",
    summary="List channel connection status",
    description="Report each inbound channel's connection state and last sync. "
    "Push channels report unknown. No tokens or secrets.",
)
async def list_channel_status() -> ChannelStatusResponse:
    raise HTTPException(status_code=501, detail="Not implemented")
