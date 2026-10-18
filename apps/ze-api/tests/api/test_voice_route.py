"""POST /api/v0/voice/transcriptions (phase 192 US1, US2)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_api.api.deps import get_container, require_api_key
from ze_api.api.v0.voice import router as voice_router_module
from ze_api.api.v0.voice.limits import VoiceBodyLimitMiddleware
from ze_api.voice.registry import TranscriptionRegistry
from tests.conftest import FakeTranscribeClient

FIXTURES = Path(__file__).parent.parent / "fixtures" / "audio"
URL = "/api/v0/voice/transcriptions"
TEN_MB = 10 * 1024 * 1024
AUTH = {"Authorization": "Bearer test"}


def _container(models: dict | None = None, client=None):
    return SimpleNamespace(
        openrouter_client=client or FakeTranscribeClient(),
        settings=SimpleNamespace(config={"models": models or {}}),
        transcription_registry=TranscriptionRegistry(),
    )


@pytest.fixture
def container():
    return _container({"whisper": "test/whisper"})


@pytest.fixture
def model(container):
    """The fake speech client; `.calls` is empty when the model was never reached."""
    return container.openrouter_client


@pytest.fixture
def probe(ffprobe_stub):
    return ffprobe_stub(["3.400000"])


@pytest.fixture
def app(container):
    app = FastAPI()
    app.add_middleware(VoiceBodyLimitMiddleware)
    app.include_router(voice_router_module.router, prefix="/api/v0")
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[require_api_key] = lambda: None
    return app


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=AUTH,
    ) as c:
        yield c


def _wav() -> bytes:
    return (FIXTURES / "one_second.wav").read_bytes()


async def test_success_returns_transcript_and_registers_id(
    client, container, probe
):
    resp = await client.post(URL, files={"file": ("a.wav", _wav(), "audio/wav")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["transcript"] == "remind me to call Ana"
    assert body["duration_s"] == 3.4
    assert container.transcription_registry.lookup(body["transcription_id"]) == (
        "remind me to call Ana",
        3.4,
    )


async def test_uses_configured_whisper_model(client, model, probe):
    await client.post(URL, files={"file": ("a.wav", _wav(), "audio/wav")})
    assert model.calls[0]["model"] == "test/whisper"
    assert model.calls[0]["audio_format"] == "audio/wav"
    assert model.calls[0]["duration_seconds"] == 3.4


async def test_falls_back_to_default_whisper_model(app, probe):
    from ze_agents.defaults import MODEL_WHISPER

    fallback = _container()
    app.dependency_overrides[get_container] = lambda: fallback
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=AUTH
    ) as c:
        await c.post(URL, files={"file": ("a.wav", _wav(), "audio/wav")})
    assert fallback.openrouter_client.calls[0]["model"] == MODEL_WHISPER


async def test_codec_parameters_are_accepted(client, probe):
    resp = await client.post(
        URL,
        files={
            "file": (
                "a.webm",
                (FIXTURES / "stream.webm").read_bytes(),
                "audio/webm;codecs=opus",
            )
        },
    )
    assert resp.status_code == 200


async def test_missing_key_is_401(app, model, probe):
    del app.dependency_overrides[require_api_key]
    app.state.settings = SimpleNamespace(ze_api_key="secret")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        resp = await c.post(URL, files={"file": ("a.wav", _wav(), "audio/wav")})
    assert resp.status_code == 401
    assert model.calls == []


# --- failures (US2) -------------------------------------------------------


async def _post_wav(client):
    return await client.post(URL, files={"file": ("a.wav", _wav(), "audio/wav")})


def _assert_no_entry(container):
    assert len(container.transcription_registry) == 0


async def test_unsupported_type_is_415(client, container, model, probe):
    resp = await client.post(URL, files={"file": ("a.txt", b"hi", "text/plain")})
    assert resp.status_code == 415
    assert (
        resp.json()["detail"]
        == "Unsupported recording type. Use WebM, Ogg, MP4 or WAV."
    )
    assert model.calls == [] and probe.calls == []
    _assert_no_entry(container)


async def test_declared_length_over_limit_is_413_before_handler(
    client, container, model, probe
):
    resp = await client.post(
        URL,
        content=b"x" * (TEN_MB + 70 * 1024),
        headers={"content-type": "multipart/form-data; boundary=b"},
    )
    assert resp.status_code == 413
    assert resp.json()["detail"] == "That recording is too large: the limit is 10 MB."
    assert model.calls == [] and probe.calls == []
    _assert_no_entry(container)


async def test_chunked_body_over_limit_is_413_from_read_cap(
    client, container, model, probe
):
    boundary = "bnd"
    head = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="a.wav"\r\n'
        "Content-Type: audio/wav\r\n\r\n"
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()

    async def body():
        yield head
        for _ in range(11):
            yield b"x" * (1024 * 1024)
        yield tail

    resp = await client.post(
        URL,
        content=body(),
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
    )
    assert resp.status_code == 413
    assert resp.json()["detail"] == "That recording is too large: the limit is 10 MB."
    assert model.calls == [] and probe.calls == []
    _assert_no_entry(container)


async def test_too_long_is_413(client, container, ffprobe_stub, model):
    ffprobe_stub(["130.0"])
    resp = await _post_wav(client)
    assert resp.status_code == 413
    assert (
        resp.json()["detail"] == "That recording is too long: the limit is 2 minutes."
    )
    _assert_no_entry(container)


async def test_unreadable_is_422(client, container, ffprobe_stub):
    ffprobe_stub([None, None])
    resp = await _post_wav(client)
    assert resp.status_code == 422
    assert resp.json()["detail"] == "I couldn't make out the recording."
    _assert_no_entry(container)


async def test_transcription_failed_is_502(client, container, model, probe):
    model.error = RuntimeError("model down")
    resp = await _post_wav(client)
    assert resp.status_code == 502
    assert resp.json()["detail"] == "I couldn't make out the recording."
    _assert_no_entry(container)


async def test_tool_missing_is_503(client, container, ffprobe_stub, monkeypatch):
    ffprobe_stub(missing=True)
    events: list[str] = []
    monkeypatch.setattr(
        voice_router_module.log, "error", lambda event, **kw: events.append(event)
    )
    resp = await _post_wav(client)
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Voice input is not available on this server."
    assert "voice_ffmpeg_missing" in events
    _assert_no_entry(container)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"files": {"other": ("a.wav", b"x", "audio/wav")}},
        {"json": {"file": "x"}},
    ],
)
async def test_missing_file_part_is_plain_422(client, container, model, probe, kwargs):
    resp = await client.post(URL, **kwargs)
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Send the recording as a file named file."
    assert model.calls == [] and probe.calls == []
    _assert_no_entry(container)


async def test_no_authorization_header_is_refused_before_the_body_is_read(app):
    reads = 0

    async def body():
        nonlocal reads
        for _ in range(3):
            reads += 1
            yield b"x" * 1024

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        resp = await c.post(
            URL,
            content=body(),
            headers={"content-type": "multipart/form-data; boundary=b"},
        )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid API key"


async def test_chunked_body_is_cut_off_at_the_limit(app):
    """The middleware stops reading once the limit plus one chunk has arrived."""
    chunk = 1024 * 1024
    seen_bytes = 0

    scope = {
        "type": "http",
        "method": "POST",
        "path": URL,
        "headers": [
            (b"content-type", b"multipart/form-data; boundary=b"),
            (b"authorization", b"Bearer t"),
        ],
    }
    sent = 0
    total_chunks = 50

    async def receive():
        nonlocal sent, seen_bytes
        sent += 1
        more = sent < total_chunks
        seen_bytes += chunk
        return {"type": "http.request", "body": b"x" * chunk, "more_body": more}

    responses: list[dict] = []

    async def send(message):
        responses.append(message)

    async def drain_app(scope, receive, send):
        while (await receive()).get("more_body"):
            pass

    from ze_api.api.v0.voice.limits import VoiceBodyLimitMiddleware

    await VoiceBodyLimitMiddleware(drain_app)(scope, receive, send)
    assert responses[0]["status"] == 413
    assert seen_bytes <= TEN_MB + 64 * 1024 + chunk


async def test_trailing_slash_path_is_also_guarded(client, container, model, probe):
    resp = await client.post(
        URL + "/",
        content=b"x" * (TEN_MB + 70 * 1024),
        headers={"content-type": "multipart/form-data; boundary=b"},
    )
    assert resp.status_code == 413
    assert model.calls == []
