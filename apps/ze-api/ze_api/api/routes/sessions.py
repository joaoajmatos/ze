from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ze_api.api.schemas import SessionSchema
from ze_api.sessions.store import SessionStore

router = APIRouter(tags=["sessions"])


def _get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


@router.get(
    "/api/sessions",
    response_model=list[SessionSchema],
    summary="List chat sessions",
    description="Returns all chat sessions ordered by most recently active.",
)
async def list_sessions(
    store: SessionStore = Depends(_get_session_store),
) -> list[SessionSchema]:
    sessions = await store.list_all()
    return [SessionSchema.model_validate(s.__dict__) for s in sessions]
