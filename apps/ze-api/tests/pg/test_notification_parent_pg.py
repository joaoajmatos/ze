import pytest
from ze_proactive.notification_store import NotificationStore

pytestmark = pytest.mark.pg


async def _create(store: NotificationStore, **kw):
    return await store.create(
        event_type="workflow_failure",
        source="workflows",
        title="Workflow failed",
        body="Step 1 failed",
        target_type="workflow_execution",
        target_id="ex-1",
        push_class="accountability",
        urgency="high",
        format="text",
        actions=[],
        **kw,
    )


async def test_migrated_schema_stores_and_returns_the_parent(pg_pool):
    store = NotificationStore(pg_pool)
    created = await _create(store, target_parent_id="wf-1", delivery="delivered")
    assert created.target_parent_id == "wf-1"

    items, _ = await store.list_page()
    assert [(i.target_id, i.target_parent_id) for i in items] == [("ex-1", "wf-1")]


async def test_held_rows_keep_the_parent_and_old_shape_has_none(pg_pool):
    store = NotificationStore(pg_pool)
    await _create(store, target_parent_id="wf-2", delivery="held")
    await _create(store, delivery="delivered")

    held = await store.list_held()
    assert [h.target_parent_id for h in held] == ["wf-2"]
    items, _ = await store.list_page()
    assert sorted(str(i.target_parent_id) for i in items) == ["None", "wf-2"]


async def test_column_is_nullable_text_added_by_zpro005(pg_pool):
    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'notifications' AND column_name = 'target_parent_id'"
        )
        applied = {
            r["version_num"]
            for r in await conn.fetch("SELECT version_num FROM alembic_version")
        }
    assert (row["data_type"], row["is_nullable"]) == ("text", "YES")
    assert "zpro005" in applied
