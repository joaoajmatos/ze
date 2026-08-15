from __future__ import annotations

import asyncio

from ze_workspace.turn_lock import ThreadTurnLock


async def test_acquire_serializes_same_thread():
    lock = ThreadTurnLock()
    order: list[str] = []

    async def worker(name: str, sleep: float) -> None:
        async with lock.acquire("thread-1"):
            order.append(f"{name}-start")
            await asyncio.sleep(sleep)
            order.append(f"{name}-end")

    await asyncio.gather(worker("a", 0.02), worker("b", 0.0))

    # Whichever task acquires first must fully finish before the other starts.
    assert order[0].endswith("-start")
    assert order[1].endswith("-end")
    assert order[1].split("-")[0] == order[0].split("-")[0]


async def test_different_threads_do_not_block_each_other():
    lock = ThreadTurnLock()
    ran: list[str] = []

    async def worker(thread_id: str) -> None:
        async with lock.acquire(thread_id):
            ran.append(thread_id)
            await asyncio.sleep(0.01)

    await asyncio.wait_for(
        asyncio.gather(worker("thread-1"), worker("thread-2")), timeout=0.05
    )
    assert set(ran) == {"thread-1", "thread-2"}


async def test_lock_released_after_context_exits():
    lock = ThreadTurnLock()
    async with lock.acquire("thread-1"):
        pass
    # A second acquire must not block if the first was released.
    await asyncio.wait_for(lock.acquire("thread-1").__aenter__(), timeout=0.05)
