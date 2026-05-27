from fastapi import APIRouter, Depends, HTTPException

from ze.api.dependencies import get_capability_gate, get_settings
from ze.api.openapi import OPENAPI_RESPONSES_422
from ze.api.schemas import (
    AgentCapabilityConfig,
    CapabilitiesResponse,
    CapabilityModeUpdate,
    UpdateCapabilityResponse,
)
from ze.capability.gate import CapabilityGate
from ze.capability.types import Mode
from ze.settings import Settings

router = APIRouter(tags=["capabilities"])


def _effective_capabilities(
    settings: Settings,
    gate: CapabilityGate,
) -> dict[str, AgentCapabilityConfig]:
    """Merge YAML defaults with DB-backed persistent overrides."""
    cache = gate._persistent_cache or {}
    result: dict[str, AgentCapabilityConfig] = {}

    for agent, cfg in settings.agent_configs.items():
        caps = dict(cfg.get("capabilities", {}))
        for (a, intent), mode in cache.items():
            if a == agent:
                caps[intent] = mode.value
        result[agent] = AgentCapabilityConfig.model_validate(
            {"enabled": cfg.get("enabled", True), **caps},
        )
    return result


@router.get(
    "",
    response_model=CapabilitiesResponse,
    summary="List capability modes",
    description=(
        "Return effective capability modes per agent (YAML defaults merged with "
        "any persistent DB overrides)."
    ),
)
def list_capabilities(
    gate: CapabilityGate = Depends(get_capability_gate),
    settings: Settings = Depends(get_settings),
) -> CapabilitiesResponse:
    return CapabilitiesResponse(_effective_capabilities(settings, gate))


@router.put(
    "/{agent}/{intent}",
    response_model=UpdateCapabilityResponse,
    summary="Update capability mode",
    description=(
        "Set the permission mode for an agent intent. The change is persisted in "
        "the database and takes precedence over config.yaml until cleared."
    ),
    responses=OPENAPI_RESPONSES_422,
)
async def update_capability(
    agent: str,
    intent: str,
    body: CapabilityModeUpdate,
    gate: CapabilityGate = Depends(get_capability_gate),
    settings: Settings = Depends(get_settings),
) -> UpdateCapabilityResponse:
    known_agents = set(settings.agent_configs)
    if agent not in known_agents:
        raise HTTPException(status_code=422, detail=f"Unknown agent: {agent!r}")

    agent_cfg = settings.agent_configs.get(agent, {})
    known_intents = set(agent_cfg.get("intent_map", {}).keys())
    known_intents |= set(agent_cfg.get("capabilities", {}).keys())

    if intent not in known_intents:
        raise HTTPException(status_code=422, detail=f"Unknown intent {intent!r} for agent {agent!r}")

    try:
        mode = Mode(body.mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid mode: {body.mode!r}") from exc

    await gate.set_permanent(agent, intent, mode)
    effective = _effective_capabilities(settings, gate)
    return UpdateCapabilityResponse({agent: effective[agent]})
