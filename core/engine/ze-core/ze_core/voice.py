from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ze_agents.errors import (
    AudioToolMissingError,
    AudioTooLongError,
    AudioUnreadableError,
    TranscriptionFailedError,
)
from ze_core.openrouter.audio import probe_duration
from ze_core.openrouter.client import OpenRouterClient
from ze_core.telemetry.context import set_agent_context, set_flow_context
from ze_logging import get_logger

log = get_logger(__name__)


@dataclass
class Transcription:
    text: str
    duration_s: float


async def transcribe_audio(
    client: OpenRouterClient,
    data: bytes,
    mime: str,
    *,
    model: str,
    max_seconds: float = 120,
    slots: asyncio.Semaphore | None = None,
) -> Transcription:
    """Measure, gate and transcribe one recording. The audio is never stored.

    `slots` bounds how many probe and conversion subprocesses run at once.
    """
    if slots is None:
        return await _transcribe(client, data, mime, model, max_seconds)
    async with slots:
        return await _transcribe(client, data, mime, model, max_seconds)


async def _transcribe(client, data, mime, model, max_seconds) -> Transcription:
    duration = await probe_duration(data, mime)
    if duration > max_seconds:
        raise AudioTooLongError(f"Recording is {duration:.0f}s; the limit is {max_seconds:.0f}s")

    set_flow_context("transcription")
    set_agent_context("whisper")
    try:
        text = await client.transcribe(
            data, mime, model=model, duration_seconds=duration
        )
    except (AudioToolMissingError, AudioUnreadableError):
        raise
    except Exception as exc:
        log.warning("voice_transcription_failed", cause=type(exc).__name__)
        raise TranscriptionFailedError("Transcription failed") from exc
    return Transcription(text.strip(), duration)
