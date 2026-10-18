"""Tests for OpenRouterClient.transcribe()."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ze_core.openrouter.client import OpenRouterClient


@pytest.fixture
def client():
    with patch("ze_core.openrouter.client.OpenRouter", return_value=MagicMock()):
        c = OpenRouterClient(
            api_key="test-key", base_url="https://openrouter.ai/api/v1"
        )
        c.complete = AsyncMock(return_value="transcribed text")
        return c


async def test_transcribe_returns_stripped_text(client):
    client.complete = AsyncMock(return_value="  hello world  ")
    result = await client.transcribe(b"audio", "wav", model="openai/whisper-1")
    assert result == "hello world"


async def test_transcribe_sends_input_audio_block(client):
    captured: list[list] = []

    async def _complete(messages, **kwargs):
        captured.append(messages)
        return "ok"

    client.complete = _complete
    audio = b"fake ogg bytes"
    await client.transcribe(audio, "wav", model="openai/whisper-1")

    assert len(captured) == 1
    msg = captured[0][0]
    assert msg["role"] == "user"
    block = msg["content"][0]
    assert block["type"] == "input_audio"
    assert block["input_audio"]["format"] == "wav"
    assert block["input_audio"]["data"] == base64.b64encode(audio).decode()


async def test_transcribe_passes_duration_as_audio_seconds(client):
    captured: list[dict] = []

    async def _complete(messages, **kwargs):
        captured.append(kwargs)
        return "ok"

    client.complete = _complete
    await client.transcribe(
        b"audio", "wav", model="openai/whisper-1", duration_seconds=12.5
    )

    assert captured[0]["audio_seconds"] == 12.5


async def test_transcribe_passes_none_when_no_duration(client):
    captured: list[dict] = []

    async def _complete(messages, **kwargs):
        captured.append(kwargs)
        return "ok"

    client.complete = _complete
    await client.transcribe(b"audio", "wav", model="openai/whisper-1")

    assert captured[0].get("audio_seconds") is None


async def test_transcribe_normalises_mime_format(client):
    """audio/x-wav; codec=pcm → wav."""
    captured: list[list] = []

    async def _complete(messages, **kwargs):
        captured.append(messages)
        return "ok"

    client.complete = _complete
    await client.transcribe(
        b"audio", "audio/x-wav; codec=pcm", model="openai/whisper-1"
    )

    block = captured[0][0]["content"][0]
    assert block["input_audio"]["format"] == "wav"


async def test_transcribe_uses_configured_model(client):
    captured_kwargs: list[dict] = []

    async def _complete(messages, **kwargs):
        captured_kwargs.append(kwargs)
        return "ok"

    client.complete = _complete
    await client.transcribe(b"audio", "wav", model="openai/whisper-large-v3")

    assert captured_kwargs[0]["model"] == "openai/whisper-large-v3"


@pytest.mark.parametrize("fmt", ["audio/ogg;codecs=opus", "audio/mp4", "audio/webm"])
async def test_transcribe_converts_everything_but_mp3_and_wav(client, fmt):
    captured: list[list] = []

    async def _complete(messages, **kwargs):
        captured.append(messages)
        return "ok"

    client.complete = _complete
    with patch(
        "ze_core.openrouter.client.to_mp3", new=AsyncMock(return_value=b"mp3-bytes")
    ) as convert:
        await client.transcribe(b"raw", fmt, model="m")

    convert.assert_awaited_once()
    block = captured[0][0]["content"][0]["input_audio"]
    assert block["format"] == "mp3"
    assert block["data"] == base64.b64encode(b"mp3-bytes").decode()
