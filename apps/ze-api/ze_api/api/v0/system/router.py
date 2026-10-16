from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ze_api.api.deps import require_api_key
from ze_api.api.schemas import HealthResponse, UiManifestResponse

_CLIENT_VERSION = "0.1.0"
_API_VERSION = "v0"

router = APIRouter()


class VersionResponse(BaseModel):
    api_version: str
    client_version: str


@router.get(
    "/version",
    response_model=VersionResponse,
    operation_id="getVersion",
    tags=["meta"],
    summary="API and client version",
    description=(
        "Returns the API version and the matching @myguyze/ze-client package version. "
        "Public — no authentication required. Use to detect version skew between "
        "client and server."
    ),
)
def get_version() -> VersionResponse:
    return VersionResponse(api_version=_API_VERSION, client_version=_CLIENT_VERSION)


@router.get(
    "/health",
    response_model=HealthResponse,
    operation_id="healthCheck",
    tags=["meta"],
    summary="Health check",
    description=(
        "Verifies the server is reachable. Public — no authentication required. "
        "Used by the web client during onboarding and settings connection tests."
    ),
)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
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
