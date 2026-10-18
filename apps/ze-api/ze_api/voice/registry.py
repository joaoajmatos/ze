from __future__ import annotations

import time
from collections.abc import Callable
from uuid import uuid4


class TranscriptionRegistry:
    """Bounded in-process store of recent transcripts, so a voice turn can cite one."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        ttl: float = 600,
        max_entries: int = 100,
    ) -> None:
        self._clock = clock
        self._ttl = ttl
        self._max_entries = max_entries
        self._entries: dict[str, tuple[str, float, float]] = {}

    def __len__(self) -> int:
        return len(self._entries)

    def register(self, text: str, duration_s: float) -> str:
        self._sweep()
        transcription_id = uuid4().hex
        self._entries[transcription_id] = (text, duration_s, self._clock())
        while len(self._entries) > self._max_entries:
            del self._entries[next(iter(self._entries))]
        return transcription_id

    def lookup(self, transcription_id: str) -> tuple[str, float] | None:
        self._sweep()
        entry = self._entries.get(transcription_id)
        if entry is None:
            return None
        return entry[0], entry[1]

    def _sweep(self) -> None:
        cutoff = self._clock() - self._ttl
        for key in [k for k, (_, _, at) in self._entries.items() if at <= cutoff]:
            del self._entries[key]
