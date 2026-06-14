from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status

from ze_api.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


def _verify_bearer_api_key(
    request: Request,
    authorization: str | None,
) -> None:
    settings = request.app.state.settings
    bearer = (
        authorization.removeprefix("Bearer ").strip()
        if authorization and authorization.startswith("Bearer ")
        else ""
    )
    if bearer != settings.ze_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


@router.get(
    "/api/health",
    response_model=HealthResponse,
    summary="Health check",
    description=(
        "Verifies that the server is reachable and the supplied API key is valid. "
        "Used by the web client during onboarding and settings connection tests."
    ),
)
async def health(
    request: Request,
    authorization: str | None = Header(default=None),
) -> HealthResponse:
    _verify_bearer_api_key(request, authorization)
    return HealthResponse(status="ok")
