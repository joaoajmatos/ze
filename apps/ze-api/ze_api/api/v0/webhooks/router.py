from fastapi import APIRouter, HTTPException, Request, status

from ze_api.wiring.webhooks import (
    WebhookAuthError,
    WebhookDispatcher,
    WebhookSourceNotFoundError,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _get_dispatcher(request: Request) -> WebhookDispatcher:
    return request.app.state.container.webhook_dispatcher


@router.post(
    "/{source}",
    status_code=200,
    summary="Receive inbound webhook from an external source",
    description="Authenticated by the source's own signing scheme, not the Ze API key.",
    operation_id="receiveWebhook",
    response_model=dict,
)
async def receive_webhook(source: str, request: Request) -> dict:
    dispatcher = _get_dispatcher(request)
    raw_body = await request.body()
    headers = dict(request.headers)
    try:
        await dispatcher.dispatch(source, raw_body, headers)
    except WebhookAuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook authentication failed",
        )
    except WebhookSourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown webhook source: {source!r}",
        )
    return {"ok": True}
