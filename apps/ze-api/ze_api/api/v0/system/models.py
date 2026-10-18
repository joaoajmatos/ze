from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ze_api.api.deps import require_api_key
from ze_api.api.v0.system.schemas import ModelSettingsResponse

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get(
    "/system/models",
    response_model=ModelSettingsResponse,
    operation_id="getModelSettings",
    tags=["meta"],
    summary="Configured model tiers",
    description="Report whether the complexity tier is on, its bar, and each agent's "
    "full and simple model. Read-only; no secrets.",
)
async def get_model_settings() -> ModelSettingsResponse:
    raise HTTPException(status_code=501, detail="Not implemented")
