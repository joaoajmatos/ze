import asyncio
import base64

import structlog

from ze.openrouter.client import OpenRouterClient
from ze.telemetry.context import set_agent_context, set_flow_context
from ze.transcription.types import TranscriptionResult

# Formats gpt-audio accepts in input_audio messages
_SUPPORTED_FORMATS = {"mp3", "wav"}

_SYSTEM = "You are a transcription engine. Transcribe the audio exactly as spoken. Output only the transcript — no commentary, no punctuation corrections, no explanations."


async def _to_mp3(audio_bytes: bytes) -> bytes:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-i", "pipe:0", "-f", "mp3", "-q:a", "4", "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate(input=audio_bytes)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg conversion failed")
    return stdout


class TranscriptionClient:
    def __init__(
        self,
        openrouter_client: OpenRouterClient,
        model: str,
        logger: structlog.BoundLogger,
    ) -> None:
        self._client = openrouter_client
        self._model = model
        self._log = logger

    async def transcribe(
        self,
        audio_bytes: bytes,
        audio_format: str,
        duration_seconds: float | None = None,
    ) -> TranscriptionResult:
        set_flow_context("transcription")
        set_agent_context("transcription")

        if audio_format not in _SUPPORTED_FORMATS:
            audio_bytes = await _to_mp3(audio_bytes)
            audio_format = "mp3"

        message = {
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": base64.b64encode(audio_bytes).decode(),
                        "format": audio_format,
                    },
                },
                {"type": "text", "text": "Transcribe the audio."},
            ],
        }
        text = await self._client.complete(
            messages=[message],
            model=self._model,
            system=_SYSTEM,
            audio_seconds=duration_seconds,
        )
        self._log.info(
            "transcription_complete",
            model=self._model,
            audio_bytes=len(audio_bytes),
            audio_format=audio_format,
            duration_seconds=duration_seconds,
        )
        return TranscriptionResult(text=text.strip())
