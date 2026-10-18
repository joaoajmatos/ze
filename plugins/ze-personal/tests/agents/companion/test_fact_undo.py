from unittest.mock import AsyncMock, patch
from uuid import uuid4

from ze_memory.errors import StoreError
from ze_personal.agents.companion.agent import CompanionAgent
from ze_personal.agents.companion.tools import forget_fact, remember_fact


def test_companion_tool_deps_expose_memory_store():
    agent = CompanionAgent.__new__(CompanionAgent)
    agent._memory_store = AsyncMock()
    agent._notification_store = None
    assert agent.tool_deps()["memory_store"] is agent._memory_store


async def test_remember_fact_payload_carries_displaced_ids():
    store = AsyncMock()
    fact_id, old = uuid4(), uuid4()

    async def _submit(_store, items):
        items[0].fact.id = fact_id
        items[0].fact.displaced_ids = [old]

    with patch(
        "ze_personal.agents.companion.tools.submit_perception_facts",
        side_effect=_submit,
    ):
        result = await remember_fact(
            predicate="colour", value="blue", memory_store=store
        )
    assert result["undo"] == {
        "fact_id": str(fact_id),
        "restore_fact_ids": [str(old)],
    }


async def test_remember_fact_failure_has_no_undo():
    store = AsyncMock()
    with patch(
        "ze_personal.agents.companion.tools.submit_perception_facts",
        side_effect=StoreError("nope"),
    ):
        result = await remember_fact(
            predicate="colour", value="blue", memory_store=store
        )
    assert "undo" not in result


async def test_forget_fact_by_id_restores_displaced():
    store = AsyncMock()
    fid, old = uuid4(), uuid4()
    result = await forget_fact(
        memory_store=store, fact_id=str(fid), restore_fact_ids=[str(old)]
    )
    store.retract_fact_and_restore.assert_awaited_once_with(fid, [old])
    assert result == {"ok": True, "ids": [str(fid)], "restored": [str(old)]}


async def test_forget_fact_by_id_conflict_is_ok_false():
    from ze_sdk.memory import FactRestoreConflictError

    store = AsyncMock()
    store.retract_fact_and_restore = AsyncMock(
        side_effect=FactRestoreConflictError("changed")
    )
    result = await forget_fact(memory_store=store, fact_id=str(uuid4()))
    assert result["ok"] is False
    assert "changed" in result["error"]


async def test_forget_fact_bad_uuid_is_ok_false():
    store = AsyncMock()
    result = await forget_fact(memory_store=store, fact_id="not-a-uuid")
    assert result["ok"] is False
    store.retract_fact_and_restore.assert_not_called()


async def test_forget_fact_requires_exactly_one_of_query_or_id():
    store = AsyncMock()
    both = await forget_fact(query="x", fact_id=str(uuid4()), memory_store=store)
    neither = await forget_fact(memory_store=store)
    assert both["ok"] is False and neither["ok"] is False
