from __future__ import annotations

import json

from starlette.types import ASGIApp, Receive, Scope, Send

MAX_RECORDING_BYTES = 10 * 1024 * 1024
TOO_LARGE_DETAIL = "That recording is too large: the limit is 10 MB."
VOICE_PATH = "/api/v0/voice/transcriptions"

# Multipart framing around the file part.
_MULTIPART_ALLOWANCE = 64 * 1024


class VoiceBodyLimitMiddleware:
    """Refuses an oversized declared body before Starlette spools the multipart parse."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and scope["path"] == VOICE_PATH
            and self._declared_length(scope)
            > MAX_RECORDING_BYTES + _MULTIPART_ALLOWANCE
        ):
            body = json.dumps({"detail": TOO_LARGE_DETAIL}).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 413,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)

    @staticmethod
    def _declared_length(scope: Scope) -> int:
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    return int(value)
                except ValueError:
                    return 0
        return 0
