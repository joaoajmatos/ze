from __future__ import annotations

import asyncio
from typing import Any, Literal
from uuid import UUID

import jsonschema
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ze_api.api.deps import get_container, require_api_key
from ze_api.api.openapi import OPENAPI_RESPONSES_422
from ze_api.api.v0.system.schemas import UiModuleResponse
from ze_components import UI_CONTRACT_VERSION, ClaimPosture, claim_tone
from ze_components.schema import export_json_schema
from ze_logging import get_logger
from ze_plugin.ui import ModuleSubject, UiContribution, get_module
from ze_plugin.ui_validate import validate_plugin_tree

log = get_logger(__name__)

PROVIDER_TIMEOUT_S = 3.0
_SUBJECT_FOR_SLOT = {
    "mind.entity": "entity",
    "doing.run": "workflow_run",
    "governance.connections": "none",
}

router = APIRouter(tags=["ui"], dependencies=[Depends(require_api_key)])


def _plugin_name(module: UiContribution) -> str:
    return module.plugin.removeprefix("ze_").replace("_", " ").title()


def _fail(module: UiContribution, status: int, reason: str, detail: str, **extra: Any):
    log.warning(
        "ui_module_failed", module_id=module.id, plugin=module.plugin, reason=reason, **extra
    )
    return HTTPException(status_code=status, detail=detail)


def _tree_schema() -> dict:
    return {"$ref": "#/$defs/PrimitiveTree", "$defs": export_json_schema()["$defs"]}


def _recompute_tones(nodes: Any) -> None:
    """Core owns tone: a provider's own tone on a claim card is replaced."""
    if isinstance(nodes, dict):
        if nodes.get("type") == "claim_card" and isinstance(nodes.get("claim"), dict):
            nodes["tone"] = claim_tone(ClaimPosture(**nodes["claim"]))
        for value in nodes.values():
            _recompute_tones(value)
    elif isinstance(nodes, list):
        for value in nodes:
            _recompute_tones(value)


def _plugin_of(container: Any, module: UiContribution) -> Any:
    for plugin in container.plugins:
        if any(c.id == module.id for c in plugin.ui_contributions()):
            return plugin
    return None


async def _resolve_subject(
    container: Any,
    module: UiContribution,
    subject_kind: str,
    subject_id: str | None,
    parent_id: str | None,
) -> ModuleSubject:
    if subject_kind != _SUBJECT_FOR_SLOT[module.slot]:
        raise HTTPException(
            status_code=422,
            detail=f"Slot {module.slot} takes subject_kind {_SUBJECT_FOR_SLOT[module.slot]}",
        )
    if subject_kind == "none":
        return ModuleSubject(kind="none")
    try:
        record_id = UUID(subject_id or "")
        parent = UUID(parent_id) if subject_kind == "workflow_run" else None
    except ValueError:
        raise HTTPException(status_code=404, detail="Subject not found") from None
    if subject_kind == "entity":
        async with container.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT entity_type, canonical_name FROM memory_entities WHERE id = $1",
                record_id,
            )
        if row is None:
            raise HTTPException(status_code=404, detail="Subject not found")
        return ModuleSubject(
            kind="entity",
            id=str(record_id),
            label=row["canonical_name"],
            entity_type=row["entity_type"],
        )
    if parent is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    execution = await container.workflow_store.get_execution(parent, record_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    return ModuleSubject(kind="workflow_run", id=str(record_id), parent_id=str(parent))


@router.get(
    "/ui/modules/{module_id}",
    response_model=UiModuleResponse,
    operation_id="getUiModule",
    summary="Plugin module view",
    description=(
        "Returns the primitive tree one plugin module shows for a slot's subject. "
        "Ze reads the subject (an entity or a workflow run) from its own records, "
        "asks the module's provider with a 3 second limit and checks the tree: the "
        "primitive schema, tool actions bound to the plugin's own agents, and "
        "licensed claim postures. `applies: false` means the module has nothing "
        "to show for this subject."
    ),
    responses={
        **OPENAPI_RESPONSES_422,
        404: {"description": "Unknown module or subject"},
        502: {"description": "The module failed or sent a view Ze cannot show"},
        504: {"description": "The module took too long"},
    },
)
async def get_ui_module(
    module_id: str,
    request: Request,
    subject_kind: Literal["entity", "workflow_run", "none"] = Query(
        description="What the slot passes: an entity, a workflow run, or nothing"
    ),
    subject_id: str | None = Query(default=None, description="Entity or run id"),
    parent_id: str | None = Query(default=None, description="Workflow id, for a run"),
    container=Depends(get_container),
) -> UiModuleResponse:
    module = get_module(container.ui_manifest, module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Unknown module")
    subject = await _resolve_subject(container, module, subject_kind, subject_id, parent_id)
    name = _plugin_name(module)
    try:
        result = await asyncio.wait_for(module.provider(subject), PROVIDER_TIMEOUT_S)
    except TimeoutError:
        raise _fail(module, 504, "timeout", f"{name} took too long.") from None
    except Exception as exc:  # noqa: BLE001 — any provider failure is one plain line
        raise _fail(module, 502, "provider_error", f"{name} could not load.", error=str(exc)) from exc
    if not result.applies:
        return UiModuleResponse(
            module_id=module.id, applies=False, components=[], ui_version=UI_CONTRACT_VERSION
        )
    components = result.components
    try:
        jsonschema.validate(components, _tree_schema())
        validate_plugin_tree(_plugin_of(container, module) or _NoPlugin(), components)
        _recompute_tones(components)
    except Exception as exc:  # noqa: BLE001 — a bad view is refused whole
        raise _fail(
            module, 502, "invalid_view", f"{name} sent a view Ze cannot show.", error=str(exc)
        ) from exc
    return UiModuleResponse(
        module_id=module.id, applies=True, components=components, ui_version=UI_CONTRACT_VERSION
    )


class _NoPlugin:
    def agent_module_paths(self) -> list[str]:
        return []
