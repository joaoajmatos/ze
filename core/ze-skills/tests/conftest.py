from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock


def make_pool(fetchrow=None, fetch=None, execute=None):
    """Mock asyncpg pool — mirrors core/ze-worldstate/tests/conftest.py."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.fetch = AsyncMock(return_value=fetch or [])
    conn.execute = AsyncMock(return_value=execute)

    @asynccontextmanager
    async def acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = acquire
    return pool, conn


def make_httpx_response(
    status_code: int = 200, text: str = "", content: bytes | None = None
):
    """Mock httpx.Response — mirrors core/ze-browser/tests/test_browser_client.py."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.content = content if content is not None else text.encode("utf-8")

    def _raise_for_status():
        if status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                f"status {status_code}", request=MagicMock(), response=resp
            )

    resp.raise_for_status = _raise_for_status
    return resp


def make_httpx_client(get_side_effect=None, get_return_value=None) -> AsyncMock:
    """Mock httpx.AsyncClient — `async with httpx.AsyncClient() as client: client.get(...)`."""
    client = AsyncMock()
    if get_side_effect is not None:
        client.get = AsyncMock(side_effect=get_side_effect)
    else:
        client.get = AsyncMock(return_value=get_return_value or make_httpx_response())
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class FakeEmbedder:
    """Returns pre-canned unit vectors — mirrors ze-core's router test fake embedder."""

    def __init__(self, vecs: dict[str, list[float]] | None = None) -> None:
        self._vecs = vecs or {}

    def encode(self, text: str) -> list[float]:
        return self._vecs.get(text, [0.0, 0.0])
