"""HTTP client for Ze's eval endpoint."""

from __future__ import annotations

import httpx


class ZeEvalClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 90.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"x-ze-api-key": api_key}
        self._timeout = timeout

    async def chat(
        self, prompt: str, session_id: str = "eval", force_agent: str | None = None
    ) -> dict:
        body = {"prompt": prompt, "session_id": session_id}
        if force_agent:
            body["force_agent"] = force_agent
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/eval/chat",
                json=body,
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()
