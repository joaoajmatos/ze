from unittest.mock import AsyncMock, patch
from uuid import uuid4

from ze_agents.claims import Provenance
from ze_memory.errors import StoreError
from ze_personal.agents.companion.tools import forget_fact, remember_fact


async def test_remember_fact_submits_prompt_supplied_reviewed():
    store = AsyncMock()
    fact_id = uuid4()

    async def _submit(_store, items):
        item = items[0]
        assert item.provenance == Provenance.PROMPT_SUPPLIED
        assert item.fact.reviewed is True
        assert item.fact.predicate == "preference"
        item.fact.id = fact_id

    with patch(
        "ze_personal.agents.companion.tools.submit_perception_facts",
        side_effect=_submit,
    ) as submit:
        result = await remember_fact(
            predicate="preference",
            value="dark mode",
            memory_store=store,
        )
    submit.assert_awaited_once()
    assert result == {"ok": True, "id": str(fact_id)}


async def test_remember_fact_returns_ok_false_on_seam_failure():
    store = AsyncMock()
    with patch(
        "ze_personal.agents.companion.tools.submit_perception_facts",
        side_effect=StoreError("nli blocked"),
    ):
        result = await remember_fact(
            predicate="preference",
            value="dark mode",
            memory_store=store,
        )
    assert result["ok"] is False
    assert "nli blocked" in result["error"]


async def test_remember_fact_returns_ok_false_when_write_has_no_id():
    store = AsyncMock()

    async def _submit(_store, items):
        items[0].fact.id = None

    with patch(
        "ze_personal.agents.companion.tools.submit_perception_facts",
        side_effect=_submit,
    ):
        result = await remember_fact(
            predicate="preference",
            value="dark mode",
            memory_store=store,
        )
    assert result["ok"] is False


async def test_forget_fact_marks_matching_ids():
    store = AsyncMock()
    fact_id = uuid4()
    store._retract_facts_matching = AsyncMock(return_value=[fact_id])
    result = await forget_fact(query="dark mode", memory_store=store)
    store._retract_facts_matching.assert_awaited_once_with("dark mode")
    assert result == {"ok": True, "ids": [str(fact_id)]}


async def test_forget_fact_miss_is_ok_false():
    store = AsyncMock()
    store._retract_facts_matching = AsyncMock(return_value=[])
    result = await forget_fact(query="never stored", memory_store=store)
    assert result["ok"] is False
    assert result["error"] == "no matching fact"


async def test_forget_empty_query_is_ok_false():
    store = AsyncMock()
    result = await forget_fact(query="   ", memory_store=store)
    assert result["ok"] is False
    store._retract_facts_matching.assert_not_called()
