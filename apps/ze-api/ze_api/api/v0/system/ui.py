from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ze_api.api.deps import require_api_key
from ze_api.api.v0.system.schemas import UiManifestResponse

# Mounted apart from `router` so the generated client keeps its method order.
ui_router = APIRouter()


@ui_router.get(
    "/ui/manifest",
    response_model=UiManifestResponse,
    operation_id="getUiManifest",
    summary="UI shell manifest",
    description=(
        "Returns plugin-contributed nav entries and settings sections. "
        "Core routes (chat, goals, settings) are not included — they are "
        "hardcoded in the web client."
    ),
    tags=["ui"],
)
async def get_ui_manifest(
    request: Request,
    _: str = Depends(require_api_key),
) -> UiManifestResponse:
    manifest = request.app.state.container.ui_manifest
    return UiManifestResponse.from_domain(manifest)
