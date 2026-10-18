from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_core.conversation.messages import PostgresMessageStore
from ze_core.conversation.messages.types import InputTrace, MessageTrace


def _trace(**kwargs) -> MessageTrace:
    return MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.2,
        is_compound=False,
        subtasks=[],
        **kwargs,
    )


def _store(stored: dict | None = None):
    """A store whose pool returns whatever `save_trace` wrote last."""
    written: dict = {}

    async def execute(sql, payload, message_id):
        written["trace"] = json.dumps(payload)

    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=execute)

    async def fetchrow(sql, message_id):
        return {"trace": written["trace"] if stored is None else stored}

    conn.fetchrow = AsyncMock(side_effect=fetchrow)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=ctx)
    return PostgresMessageStore(pool)


def test_input_trace_round_trips_through_asdict():
    trace = InputTrace(modality="voice", duration_s=3.4, edited=True)
    assert InputTrace(**asdict(trace)) == trace


def test_message_trace_input_defaults_to_none():
    assert _trace().input is None


async def test_store_round_trip_keeps_voice_input():
    store = _store()
    trace = _trace(input=InputTrace(modality="voice", duration_s=3.4, edited=False))
    await store.save_trace(uuid4(), trace)
    loaded = await store.get_trace(uuid4())
    assert loaded is not None
    assert loaded.input == InputTrace(modality="voice", duration_s=3.4, edited=False)


async def test_store_round_trip_keeps_text_trace_input_none():
    store = _store()
    await store.save_trace(uuid4(), _trace())
    loaded = await store.get_trace(uuid4())
    assert loaded is not None
    assert loaded.input is None


async def test_row_without_input_key_parses_with_none():
    data = asdict(_trace())
    del data["input"]
    store = _store(stored=json.dumps(data))
    loaded = await store.get_trace(uuid4())
    assert loaded is not None
    assert loaded.input is None
