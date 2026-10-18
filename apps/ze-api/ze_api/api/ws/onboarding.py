from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ze_components import UI_CONTRACT_VERSION
from ze_api.api.ws.connection import ConnectionManager
from ze_onboarding import OnboardingView


async def send_onboarding_view(
    conn_mgr: ConnectionManager,
    view: OnboardingView,
) -> None:
    await conn_mgr.send_frame(
        {
            "type": "message",
            "ui_version": UI_CONTRACT_VERSION,
            "message": {
                "id": str(uuid4()),
                "role": "assistant",
                "text": view.text,
                "components": view.components,
                "read": False,
                "thread_id": f"onboarding:{view.session_id}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "onboarding": {
                "session_id": str(view.session_id),
                "completed": view.completed,
            },
        }
    )
