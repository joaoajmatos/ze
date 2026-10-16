from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ze_api.api.dependencies import (
    get_held_write_resumer,
    get_held_write_store,
    require_api_key,
)
from ze_api.api.schemas import (
    HeldWriteDecisionIn,
    HeldWriteListResponse,
    HeldWriteOut,
)
from ze_automation import rest as automation_rest
from ze_automation.holds.resumer import (
    HeldWriteEditError,
    HeldWriteNotFoundError,
    HeldWriteNotOpenError,
)
from ze_automation.holds.types import HeldWriteStatus
from ze_logging import get_logger

log = get_logger(__name__)

router = APIRouter(
    prefix="/held-writes",
    tags=["held-writes"],
    dependencies=[Depends(require_api_key)],
)


@router.get(
    "",
    response_model=HeldWriteListResponse,
    operation_id="listHeldWrites",
    summary="List held writes",
    description=(
        "Return the writes an unattended workflow or goal run is holding for the "
        "user's approval. Defaults to the open ones."
    ),
)
async def list_held_writes(
    status: HeldWriteStatus = Query(HeldWriteStatus.OPEN),
    store=Depends(get_held_write_store),
) -> HeldWriteListResponse:
    rows = await automation_rest.list_held_writes(store, status)
    return HeldWriteListResponse(items=[HeldWriteOut.model_validate(r) for r in rows])


@router.post(
    "/{request_id}/decision",
    response_model=HeldWriteOut,
    operation_id="decideHeldWrite",
    summary="Approve or deny a held write",
    description=(
        "Answer a held write. Approve runs the exact held call and continues the run; "
        "deny continues it with a declined result. The run resumes in the background. "
        "404 when the id is unknown, 409 when it was already decided or expired."
    ),
)
async def decide_held_write(
    request_id: str,
    body: HeldWriteDecisionIn,
    request: Request,
    resumer=Depends(get_held_write_resumer),
) -> HeldWriteOut:
    try:
        hold = await resumer.decide(request_id, body.choice, body.edits)
    except HeldWriteNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Held write not found") from exc
    except HeldWriteNotOpenError as exc:
        raise HTTPException(status_code=409, detail="Held write is not open") from exc
    except HeldWriteEditError as exc:
        raise HTTPException(status_code=422, detail="invalid edit") from exc
    log.info(
        "held_write_answered", request_id=request_id, choice=body.choice, via="rest"
    )
    resumer.resume_in_background(hold, body.choice, body.edits)
    container = request.app.state.container
    await container.connection_manager.send_frame(
        {"type": "confirm_cancel", "id": request_id}
    )
    return HeldWriteOut.model_validate(automation_rest.held_write_to_dict(hold))
