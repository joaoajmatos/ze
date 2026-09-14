from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator


class ThreadTurnLock:
    """One asyncio.Lock per thread_id so at most one turn runs on a conversation
    at a time — held around every invoke_raw_turn/resume_turn call so a
    follow-through follow-up never lands mid another reply (FR-008)."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, thread_id: str) -> asyncio.Lock:
        lock = self._locks.get(thread_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[thread_id] = lock
        return lock

    @asynccontextmanager
    async def acquire(self, thread_id: str) -> AsyncIterator[None]:
        lock = self._lock_for(thread_id)
        await lock.acquire()
        try:
            yield
        finally:
            lock.release()
