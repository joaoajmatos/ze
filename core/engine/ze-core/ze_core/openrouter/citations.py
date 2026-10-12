"""Capture OpenRouter web-search citations the SDK's response models drop.

OpenRouter returns `url_citation` annotations on the assistant message (or on
streamed deltas). The SDK's models have no `annotations` field, so they are lost
at parse time. CitationTransport tees the raw response body instead.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

import httpx
from ze_agents.types import Source, add_sources

_holder: ContextVar[list[Source] | None] = ContextVar("citation_holder", default=None)


@contextmanager
def capture_citations() -> Iterator[list[Source]]:
    """Collect citations from every chat response made in this task."""
    found: list[Source] = []
    token = _holder.set(found)
    try:
        yield found
    finally:
        _holder.reset(token)


def parse_annotations(annotations: Any) -> list[Source]:
    sources: list[Source] = []
    for item in annotations or []:
        if not isinstance(item, dict) or item.get("type") != "url_citation":
            continue
        citation = item.get("url_citation")
        if not isinstance(citation, dict) or not citation.get("url"):
            continue
        sources.append(
            Source(url=str(citation["url"]), title=str(citation.get("title") or ""))
        )
    return sources


def _from_payload(payload: Any) -> list[Source]:
    if not isinstance(payload, dict):
        return []
    sources: list[Source] = []
    for choice in payload.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        for key in ("message", "delta"):
            part = choice.get(key)
            if isinstance(part, dict):
                add_sources(sources, parse_annotations(part.get("annotations")))
    return sources


class _TeeStream(httpx.AsyncByteStream):
    def __init__(self, inner: httpx.AsyncByteStream, sink: list[Source], sse: bool):
        self._inner = inner
        self._sink = sink
        self._sse = sse
        self._buffer = b""

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in self._inner:
            self._feed(chunk)
            yield chunk
        self._finish()

    async def aclose(self) -> None:
        await self._inner.aclose()

    def _feed(self, chunk: bytes) -> None:
        self._buffer += chunk
        if not self._sse:
            return
        *lines, self._buffer = self._buffer.split(b"\n")
        for line in lines:
            self._read_line(line)

    def _finish(self) -> None:
        if self._sse:
            self._read_line(self._buffer)
            return
        try:
            add_sources(self._sink, _from_payload(json.loads(self._buffer)))
        except ValueError:
            pass

    def _read_line(self, line: bytes) -> None:
        text = line.strip()
        if not text.startswith(b"data: {") or b"annotations" not in text:
            return
        try:
            add_sources(self._sink, _from_payload(json.loads(text[6:])))
        except ValueError:
            pass


class CitationTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner: httpx.AsyncBaseTransport | None = None) -> None:
        self._inner = inner or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        sink = _holder.get()
        capturing = sink is not None and request.url.path.endswith("/chat/completions")
        if capturing:
            # The tee sees wire bytes, before httpx decodes them.
            request.headers["accept-encoding"] = "identity"
        response = await self._inner.handle_async_request(request)
        if not capturing:
            return response
        sse = "text/event-stream" in response.headers.get("content-type", "")
        response.stream = _TeeStream(response.stream, sink, sse)  # type: ignore[arg-type]
        return response

    async def aclose(self) -> None:
        await self._inner.aclose()
