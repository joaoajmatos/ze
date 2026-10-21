"""The shared frame fixture builds the shapes in contracts/scripts.md."""

from __future__ import annotations

import asyncio

import pytest

from tests.fixtures.script_frames import (
    END_STATUSES,
    FakeScriptSidecar,
    WaitForZe,
    call_frame,
    cancel_frame,
    end_frame,
    reply_frame,
    start_frame,
)


def test_frames_match_the_contract() -> None:
    assert start_frame("id", "src", "stub", 5) == {
        "type": "start", "id": "id", "source": "src", "stub": "stub", "timeout_seconds": 5,
    }
    assert call_frame(1, "t", {"a": 1}) == {"type": "call", "seq": 1, "tool": "t", "args": {"a": 1}}
    assert reply_frame(1, value=[1]) == {"type": "reply", "seq": 1, "ok": True, "value": [1]}
    assert reply_frame(2, ok=False, error="boom") == {
        "type": "reply", "seq": 2, "ok": False, "error": "boom",
    }
    assert cancel_frame() == {"type": "cancel"}
    assert set(end_frame("busy")) == {
        "type", "status", "value", "writes", "stderr_tail", "exception",
    }
    assert len(END_STATUSES) == 8
    with pytest.raises(ValueError):
        end_frame("nope")


async def test_fake_sidecar_plays_frames_and_records_ze() -> None:
    fake = FakeScriptSidecar(
        [call_frame(1, "t"), WaitForZe("reply"), end_frame("ok", value=3)]
    )
    async with fake.connect("ws://x/scripts", max_size=1) as sock:
        first = await sock.recv()
        assert '"call"' in first
        waiter = asyncio.create_task(sock.recv())
        await asyncio.sleep(0)
        assert not waiter.done()
        await sock.send('{"type": "reply", "seq": 1, "ok": true, "value": 1}')
        assert '"end"' in await waiter
    assert fake.socket.closed
    assert fake.socket.sent_of("reply")[0]["seq"] == 1
    assert fake.connects[0]["max_size"] == 1
