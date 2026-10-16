from fastapi import APIRouter

from ze_api.api.ws.connection import ConnectionManager
from ze_api.api.ws.confirmation import (
    confirmation_timeout,
    handle_confirm,
    notify_confirmation_request,
    send_confirmation_request,
)
from ze_api.api.ws.onboarding import send_onboarding_view
from ze_api.api.ws.endpoint import websocket_endpoint
from ze_api.api.ws.serializers import extract_thread_id, message_to_dict

router = APIRouter(tags=["websocket"])
router.add_api_websocket_route("/ws", websocket_endpoint)

__all__ = [
    "ConnectionManager",
    "confirmation_timeout",
    "extract_thread_id",
    "handle_confirm",
    "message_to_dict",
    "notify_confirmation_request",
    "send_confirmation_request",
    "router",
    "send_onboarding_view",
]
