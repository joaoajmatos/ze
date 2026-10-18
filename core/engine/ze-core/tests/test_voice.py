"""transcribe_audio — probe, length gate, model call, cost context."""

import pytest

from ze_agents.errors import (
    AudioToolMissingError,
    AudioTooLongError,
    AudioUnreadableError,
    TranscriptionFailedError,
)
from ze_core import voice
from ze_core.voice import Transcription, transcribe_audio


@pytest.fixture
def probe(monkeypatch):
    seen: list[tuple] = []

    def install(duration: float):
        async def fake(data, mime, **_):
            seen.append((data, mime))
            return duration

        monkeypatch.setattr(voice, "probe_duration", fake)
        return seen

    return install


async def test_success_strips_text_and_passes_duration(probe, fake_transcribe_client):
    probe(3.4)
    fake_transcribe_client.reply = "  hello there \n"
    result = await transcribe_audio(
        fake_transcribe_client, b"abc", "audio/webm;codecs=opus", model="m"
    )
    assert result == Transcription("hello there", 3.4)
    call = fake_transcribe_client.calls[0]
    assert call["audio_bytes"] == b"abc"
    assert call["audio_format"] == "audio/webm;codecs=opus"
    assert call["duration_seconds"] == 3.4
    assert call["model"] == "m"


async def test_empty_reply_returns_empty_text(probe, fake_transcribe_client):
    probe(2.0)
    fake_transcribe_client.reply = "   "
    result = await transcribe_audio(fake_transcribe_client, b"a", "audio/wav", model="m")
    assert result == Transcription("", 2.0)


async def test_over_max_seconds_raises_before_model_call(probe, fake_transcribe_client):
    probe(121.0)
    with pytest.raises(AudioTooLongError):
        await transcribe_audio(fake_transcribe_client, b"a", "audio/wav", model="m")
    assert fake_transcribe_client.calls == []


async def test_exactly_max_seconds_is_allowed(probe, fake_transcribe_client):
    probe(120.0)
    result = await transcribe_audio(fake_transcribe_client, b"a", "audio/wav", model="m")
    assert result.duration_s == 120.0


async def test_model_error_becomes_transcription_failed(
    probe, fake_transcribe_client
):
    probe(1.0)
    fake_transcribe_client.error = RuntimeError("boom")
    with pytest.raises(TranscriptionFailedError) as info:
        await transcribe_audio(fake_transcribe_client, b"a", "audio/wav", model="m")
    assert isinstance(info.value.__cause__, RuntimeError)


async def test_flow_and_agent_context_during_call(
    probe, fake_transcribe_client, monkeypatch
):
    probe(1.0)
    calls: list[tuple] = []
    monkeypatch.setattr(
        voice, "set_flow_context", lambda *a, **k: calls.append(("flow", a))
    )
    monkeypatch.setattr(
        voice, "set_agent_context", lambda *a, **k: calls.append(("agent", a))
    )
    await transcribe_audio(fake_transcribe_client, b"a", "audio/wav", model="m")
    assert ("flow", ("transcription",)) in calls
    assert ("agent", ("whisper",)) in calls


@pytest.mark.parametrize("error", [AudioToolMissingError("no ffmpeg"), AudioUnreadableError("bad")])
async def test_conversion_errors_are_not_model_failures(probe, fake_transcribe_client, error):
    probe(1.0)
    fake_transcribe_client.error = error
    with pytest.raises(type(error)):
        await transcribe_audio(fake_transcribe_client, b"a", "audio/webm", model="m")
