from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock


def make_pool(fetchrow=None, fetch=None, execute=None):
    """Mock asyncpg pool — mirrors core/ze-skills/tests/conftest.py."""
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
    status_code: int = 200,
    json_data: dict | None = None,
    text: str = "",
    content: bytes | None = None,
):
    """Mock httpx.Response for WorkspaceClient tests."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.content = content if content is not None else text.encode("utf-8")
    resp.json = MagicMock(return_value=json_data or {})

    def _raise_for_status():
        if status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                f"status {status_code}", request=MagicMock(), response=resp
            )

    resp.raise_for_status = _raise_for_status
    return resp


def make_httpx_client(
    *,
    get_side_effect=None,
    get_return_value=None,
    post_side_effect=None,
    post_return_value=None,
    put_side_effect=None,
    put_return_value=None,
    delete_side_effect=None,
    delete_return_value=None,
) -> AsyncMock:
    """Mock httpx.AsyncClient used by WorkspaceClient."""
    client = AsyncMock()
    if get_side_effect is not None:
        client.get = AsyncMock(side_effect=get_side_effect)
    else:
        client.get = AsyncMock(return_value=get_return_value or make_httpx_response())
    if post_side_effect is not None:
        client.post = AsyncMock(side_effect=post_side_effect)
    else:
        client.post = AsyncMock(return_value=post_return_value or make_httpx_response())
    if put_side_effect is not None:
        client.put = AsyncMock(side_effect=put_side_effect)
    else:
        client.put = AsyncMock(return_value=put_return_value or make_httpx_response())
    if delete_side_effect is not None:
        client.delete = AsyncMock(side_effect=delete_side_effect)
    else:
        client.delete = AsyncMock(
            return_value=delete_return_value or make_httpx_response()
        )
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.aclose = AsyncMock()
    return client
