from __future__ import annotations

from fastapi import APIRouter

from ze_api.api.v0.system.schemas import HealthResponse, VersionResponse

_CLIENT_VERSION = "0.1.0"
_API_VERSION = "v0"

router = APIRouter()


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
