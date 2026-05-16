from fastapi import APIRouter, Depends, HTTPException

from ze.api.dependencies import get_capability_gate, get_settings
from ze.api.schemas import CapabilityModeUpdate
from ze.capability.gate import CapabilityGate
from ze.settings import Settings

router = APIRouter(tags=["capabilities"])


@router.get("")
def list_capabilities(gate: CapabilityGate = Depends(get_capability_gate)) -> dict:
    return gate._config.get("capabilities", {})


@router.put("/{agent}/{intent}")
def update_capability(
    agent: str,
    intent: str,
    body: CapabilityModeUpdate,
    gate: CapabilityGate = Depends(get_capability_gate),
    settings: Settings = Depends(get_settings),
) -> dict:
    known_agents = set(settings.agent_configs)
    if agent not in known_agents:
        raise HTTPException(status_code=422, detail=f"Unknown agent: {agent!r}")

    agent_cfg = settings.agent_configs.get(agent, {})
    known_intents = set(agent_cfg.get("intent_map", {}).keys())
    # Also accept intents from capabilities config
    cap_cfg = gate._config.get("capabilities", {}).get(agent, {})
    known_intents |= {k for k in cap_cfg if k not in ("enabled",)}

    if intent not in known_intents:
        raise HTTPException(status_code=422, detail=f"Unknown intent {intent!r} for agent {agent!r}")

    gate.update_permanent(agent, intent, body.mode)
    return {agent: gate._config.get("capabilities", {}).get(agent, {})}
