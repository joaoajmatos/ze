from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ze_api.api.datetimes import require_aware
from ze_api.api.deps import get_loop_store, require_api_key
from ze_api.api.v0.loops.schemas import (
    LoopListItem,
    LoopStateName,
    LoopTransitionResponse,
)
from ze_worldstate import rest as loop_rest
from ze_worldstate.errors import InvalidLoopTransitionError, LoopNotFoundError
from ze_worldstate.store import LoopStore

router = APIRouter(
    prefix="/loops", tags=["loops"], dependencies=[Depends(require_api_key)]
)


@router.get(
    "",
    response_model=list[LoopListItem],
    operation_id="listLoops",
    summary="List open loops",
    description="Return open loops, optionally filtered to one or more lifecycle "
    "states (repeat `state`) and to loops updated after `since` (a timezone offset is required; use Z or %2B00:00 in a URL). Defaults to "
    "non-terminal states (suspected, active, drifting). Each item "
    "reports whether the loop was promoted by corroboration and the distinct "
    "inflows it was seen in. `claim_kind` follows the state: suspicion while "
    "suspected, priority once active, drifting or closed, and null for dropped loops.",
)
async def list_loops(
    state: list[LoopStateName] | None = Query(default=None),
    since: datetime | None = Query(default=None),
    store: LoopStore = Depends(get_loop_store),
) -> list[LoopListItem]:
    require_aware(since=since)
    loops = await loop_rest.list_loops(store, state or None, since=since)
    return [LoopListItem.model_validate(loop) for loop in loops]


@router.post(
    "/{loop_id}/confirm",
    response_model=LoopTransitionResponse,
    operation_id="confirmLoop",
    summary="Confirm a suspected loop",
    description="Transition a suspected loop to active (FR-007, FR-015).",
)
async def confirm_loop(
    loop_id: UUID,
    store: LoopStore = Depends(get_loop_store),
) -> LoopTransitionResponse:
    try:
        result = await loop_rest.confirm_loop(store, loop_id)
    except LoopNotFoundError:
        raise HTTPException(status_code=404, detail="Loop not found")
    except InvalidLoopTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return LoopTransitionResponse.model_validate(result)


@router.post(
    "/{loop_id}/close",
    response_model=LoopTransitionResponse,
    operation_id="closeLoop",
    summary="Close a loop",
    description="Transition an active or drifting loop to closed (done) (FR-015).",
)
async def close_loop(
    loop_id: UUID,
    store: LoopStore = Depends(get_loop_store),
) -> LoopTransitionResponse:
    try:
        result = await loop_rest.close_loop(store, loop_id)
    except LoopNotFoundError:
        raise HTTPException(status_code=404, detail="Loop not found")
    except InvalidLoopTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return LoopTransitionResponse.model_validate(result)


@router.post(
    "/{loop_id}/drop",
    response_model=LoopTransitionResponse,
    operation_id="dropLoop",
    summary="Drop a loop",
    description="Transition any non-terminal loop to dropped (not real / no longer "
    "relevant / dismiss) (FR-007, FR-015). Records the evidence fingerprint so the "
    "same evidence does not resurface the loop later (FR-011).",
)
async def drop_loop(
    loop_id: UUID,
    store: LoopStore = Depends(get_loop_store),
) -> LoopTransitionResponse:
    try:
        result = await loop_rest.drop_loop(store, loop_id)
    except LoopNotFoundError:
        raise HTTPException(status_code=404, detail="Loop not found")
    except InvalidLoopTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return LoopTransitionResponse.model_validate(result)
