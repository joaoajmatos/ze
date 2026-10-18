from __future__ import annotations

from dataclasses import dataclass

from ze_core.openrouter.client import OpenRouterClient


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
) -> Transcription:
    raise NotImplementedError
