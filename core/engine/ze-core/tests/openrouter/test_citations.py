import json

import httpx
from ze_agents.types import Source
from ze_core.openrouter.citations import (
    CitationTransport,
    capture_citations,
    parse_annotations,
)


def _annotation(url: str, title: str = "T") -> dict:
    return {
        "type": "url_citation",
        "url_citation": {"url": url, "title": title, "start_index": 0, "end_index": 0},
    }


def _response(content: bytes, content_type: str = "application/json") -> httpx.Response:
    # stream-backed, like a real transport (content= would be pre-read)
    return httpx.Response(
        200,
        headers={"content-type": content_type},
        stream=httpx.ByteStream(content),
    )


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=CitationTransport(httpx.MockTransport(handler)))


def test_parse_annotations_keeps_url_citations_only():
    found = parse_annotations(
        [
            _annotation("https://a.test", "A"),
            {"type": "file_citation"},
            {"type": "url_citation", "url_citation": {"title": "no url"}},
            "junk",
        ]
    )
    assert found == [Source(url="https://a.test", title="A")]


async def test_non_streaming_response_is_captured():
    body = {
        "choices": [
            {
                "message": {
                    "content": "hi",
                    "annotations": [_annotation("https://a.test", "A")],
                }
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _response(json.dumps(body).encode())

    async with _client(handler) as client:
        with capture_citations() as found:
            resp = await client.post("https://x.test/api/v1/chat/completions", json={})
    assert resp.json() == body
    assert found == [Source(url="https://a.test", title="A")]


async def test_streaming_response_is_captured_and_passed_through():
    chunks = [
        {"choices": [{"delta": {"content": "hel"}}]},
        {"choices": [{"delta": {"annotations": [_annotation("https://a.test")]}}]},
        {"choices": [{"delta": {"annotations": [_annotation("https://a.test")]}}]},
        {"choices": [{"delta": {"annotations": [_annotation("https://b.test")]}}]},
    ]
    sse = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return _response(sse.encode(), "text/event-stream")

    async with _client(handler) as client:
        with capture_citations() as found:
            async with client.stream(
                "POST", "https://x.test/api/v1/chat/completions", json={}
            ) as resp:
                text = "".join([line async for line in resp.aiter_text()])
    assert text == sse
    assert [s.url for s in found] == ["https://a.test", "https://b.test"]


async def test_nothing_captured_outside_a_capture_scope():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    async with _client(handler) as client:
        resp = await client.post("https://x.test/api/v1/chat/completions", json={})
    assert resp.status_code == 200


async def test_other_endpoints_are_not_inspected():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = {"choices": [{"message": {"annotations": [_annotation("https://a.test")]}}]}
        return _response(json.dumps(payload).encode())

    async with _client(handler) as client:
        with capture_citations() as found:
            await client.get("https://x.test/api/v1/generation")
    assert found == []


async def test_captured_requests_ask_for_unencoded_bodies():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["accept-encoding"])
        return _response(b"{}")

    async with _client(handler) as client:
        with capture_citations():
            await client.post("https://x.test/api/v1/chat/completions", json={})
    assert seen == ["identity"]
