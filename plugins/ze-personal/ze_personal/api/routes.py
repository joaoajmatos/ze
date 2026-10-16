from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ze_personal.api.schemas import PluginPageResponse
from ze_personal.ui.page import build_contacts_page
from ze_sdk.api import require_api_key

router = APIRouter(
    prefix="/api/v0", tags=["contacts"], dependencies=[Depends(require_api_key)]
)


def _page_title(count: int) -> str:
    if count == 0:
        return "People"
    if count == 1:
        return "1 person"
    return f"{count} people"


@router.get(
    "/contacts/page",
    response_model=PluginPageResponse,
    operation_id="getContactsPage",
    summary="Contacts overview page",
    description="Returns the server-driven UI tree for the contacts management screen.",
)
async def get_contacts_page(request: Request) -> PluginPageResponse:
    store = request.app.state.container._plugin_stores.get("person_store")
    if store is None:
        return PluginPageResponse(title="People", tree=build_contacts_page([]))

    people = [p for p in await store.list_confirmed() if p.id is not None]
    return PluginPageResponse(
        title=_page_title(len(people)),
        tree=build_contacts_page(people),
    )
