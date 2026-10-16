"""SignalSource protocol — Phase 60.

Plugin authors implement this to contribute signals to the correlation/admission
pipeline without touching the engine internals.  Re-exported via ``ze_sdk.memory``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, TypeVar, runtime_checkable

SignalT_co = TypeVar("SignalT_co", covariant=True)


@runtime_checkable
class SignalSource(Protocol[SignalT_co]):
    """A plugin-provided source of candidate signals.

    The admission gate (Phase 56) decides which polled signals are ingested.
    Sources are collected by the container via ``ZePlugin.signal_sources()`` and
    deduplicated by ``source_key``. ``ze-plugin`` does not depend on ``ze-memory``,
    so the signal type is a parameter; plugins return ``ze_memory.types.Signal``.
    """

    source_key: str

    async def poll(self, since: datetime) -> list[SignalT_co]:
        """Return candidate signals produced since ``since``.

        The caller owns the watermark; sources need not persist it themselves.
        Return an empty list when nothing new is available.
        """
        ...
