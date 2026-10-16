from __future__ import annotations

from ze_proactive.types import PushKind

CONFIRMATION_REQUEST = PushKind(
    "confirmation_request", "accountability", "high", "conversation", in_chat=False
)
CONFIRMATION_TIMEOUT = PushKind(
    "confirmation_timeout", "accountability", "low", "conversation"
)
