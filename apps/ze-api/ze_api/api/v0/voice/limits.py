from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_RECORDING_BYTES = 10 * 1024 * 1024
TOO_LARGE_DETAIL = "That recording is too large: the limit is 10 MB."
VOICE_PATH = "/api/v0/voice/transcriptions"

# Multipart framing around the file part.
_MULTIPART_ALLOWANCE = 64 * 1024
_MAX_BODY_BYTES = MAX_RECORDING_BYTES + _MULTIPART_ALLOWANCE


class VoiceBodyLimitMiddleware:
    """Bounds the voice upload before Starlette spools the multipart parse.

    FastAPI reads the form before it resolves `require_api_key`, so a missing
    Authorization header is refused here, and the bytes actually received are
    counted so a chunked body with no Content-Length is cut off too.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self._is_voice_upload(scope):
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        if b"authorization" not in headers:
            await self._refuse(send, 401, "Invalid API key")
            return
        if self._declared_length(headers) > _MAX_BODY_BYTES:
            await self._refuse(send, 413, TOO_LARGE_DETAIL)
            return

        received = 0
        refused = False

        async def counting_receive() -> Message:
            nonlocal received, refused
            if refused:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > _MAX_BODY_BYTES:
                    # FastAPI turns a parse failure into a 400, so answer here and
                    # tell the app the client is gone.
                    refused = True
                    await self._refuse(send, 413, TOO_LARGE_DETAIL)
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            if not refused:
                await send(message)

        await self.app(scope, counting_receive, guarded_send)

    @staticmethod
    def _is_voice_upload(scope: Scope) -> bool:
        return (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and scope["path"].rstrip("/") == VOICE_PATH
        )

    @staticmethod
    def _declared_length(headers: dict[bytes, bytes]) -> int:
        try:
            return int(headers.get(b"content-length", b"0"))
        except ValueError:
            return 0

    @staticmethod
    async def _refuse(send: Send, status: int, detail: str) -> None:
        body = json.dumps({"detail": detail}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
