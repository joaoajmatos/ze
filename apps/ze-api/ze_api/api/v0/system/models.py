from __future__ import annotations

from fastapi import APIRouter, Depends
from ze_agents.registry import get_enabled_agents

from ze_api.api.deps import get_container, require_api_key
from ze_api.api.v0.system.schemas import AgentModelSetting, ModelSettingsResponse
from ze_core.routing.tier import ComplexitySurfaceConfig, resolve_agent_model

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
async def get_model_settings(container=Depends(get_container)) -> ModelSettingsResponse:
    config = container.settings.config
    surface = ComplexitySurfaceConfig.from_settings(config)
    agents = get_enabled_agents()
    return ModelSettingsResponse(
        complexity_enabled=surface.calibrated,
        simple_max=surface.simple_max,
        agents=[
            AgentModelSetting(
                name=name,
                model=resolve_agent_model(name, "full", config),
                model_simple=(
                    resolve_agent_model(name, "simple", config)
                    if agents[name].model_simple
                    else None
                ),
            )
            for name in sorted(agents)
        ],
    )
