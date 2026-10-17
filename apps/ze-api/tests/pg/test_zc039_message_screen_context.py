from datetime import UTC, datetime
from uuid import uuid4

import pytest
from ze_core.conversation.messages import Message, PostgresMessageStore

pytestmark = pytest.mark.pg


async def test_screen_context_round_trips_on_the_user_message(pg_pool):
    ctx = {
        "place": "doing",
        "subject": [{"kind": "workflow", "id": "w1", "label": "Café"}],
    }
    thread = f"zc039-{uuid4().hex}"
    store = PostgresMessageStore(pg_pool)
    user = Message(
        id=uuid4(),
        role="user",
        text="why?",
        components=[],
        read=True,
        created_at=datetime.now(UTC),
        thread_id=thread,
        screen_context=ctx,
    )
    plain = Message(
        id=uuid4(),
        role="assistant",
        text="because",
        components=[],
        read=True,
        created_at=datetime.now(UTC),
        thread_id=thread,
    )
    await store.save(user)
    await store.save(plain)

    loaded = await store.get_message(user.id)
    assert loaded is not None and loaded.screen_context == ctx
    other = await store.get_message(plain.id)
    assert other is not None and other.screen_context is None
