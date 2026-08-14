from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from ze_skills.store import PostgresSkillStore
from ze_skills.types import ReferenceFile, Skill, SkillSource, SkillStatus

from tests.conftest import make_pool


def _row(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid4(),
        name="Pirate Speak",
        slug="pirate-speak",
        description="Ends every response with Arrr!",
        instructions="Always end with Arrr!",
        source="imported",
        origin_url="http://example.com/SKILL.md",
        bundling_plugin=None,
        status="pending_review",
        allowed_tools=None,
        has_scripts=False,
        executable_approved=False,
        executable_approved_at=None,
        content_hash="abc123",
        created_at=now,
        approved_at=None,
        last_checked_at=None,
        last_check_error=None,
    )
    defaults.update(overrides)
    return defaults


@pytest.mark.asyncio
async def test_create_inserts_and_returns_skill():
    pool, conn = make_pool(fetchrow=_row())
    store = PostgresSkillStore(pool)

    skill = Skill(
        name="Pirate Speak",
        description="Ends every response with Arrr!",
        instructions="Always end with Arrr!",
        source=SkillSource.IMPORTED,
        origin_url="http://example.com/SKILL.md",
    )
    result = await store.create(skill)

    assert result.name == "Pirate Speak"
    assert result.status == SkillStatus.PENDING_REVIEW
    conn.fetchrow.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_returns_none_when_missing():
    pool, conn = make_pool(fetchrow=None)
    store = PostgresSkillStore(pool)

    result = await store.get(uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_get_returns_skill_when_found():
    row = _row()
    pool, conn = make_pool(fetchrow=row)
    store = PostgresSkillStore(pool)

    result = await store.get(row["id"])

    assert result is not None
    assert result.id == row["id"]
    assert result.source == SkillSource.IMPORTED


@pytest.mark.asyncio
async def test_list_applies_status_and_source_filters():
    pool, conn = make_pool(fetch=[_row()])
    store = PostgresSkillStore(pool)

    result = await store.list(status=SkillStatus.ACTIVE, source=SkillSource.IMPORTED)

    assert len(result) == 1
    args, kwargs = conn.fetch.call_args
    query = args[0]
    assert "status = $1" in query
    assert "source = $2" in query
    assert args[1:] == ("active", "imported")


@pytest.mark.asyncio
async def test_list_no_filters_returns_all():
    pool, conn = make_pool(fetch=[_row(), _row()])
    store = PostgresSkillStore(pool)

    result = await store.list()

    assert len(result) == 2
    args, _ = conn.fetch.call_args
    assert "WHERE" not in args[0]


@pytest.mark.asyncio
async def test_transition_succeeds_returns_updated_skill():
    row = _row(status="active", approved_at=datetime.now(timezone.utc))
    pool, conn = make_pool(fetchrow=row)
    store = PostgresSkillStore(pool)

    result = await store.transition(
        row["id"],
        SkillStatus.PENDING_REVIEW,
        SkillStatus.ACTIVE,
        set_approved_at=True,
    )

    assert result is not None
    assert result.status == SkillStatus.ACTIVE


@pytest.mark.asyncio
async def test_transition_fails_on_stale_status_returns_none():
    pool, conn = make_pool(fetchrow=None)
    store = PostgresSkillStore(pool)

    result = await store.transition(
        uuid4(), SkillStatus.PENDING_REVIEW, SkillStatus.ACTIVE
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_reference_file_single_lookup():
    skill_id = uuid4()
    ref_row = dict(
        id=uuid4(),
        skill_id=skill_id,
        filename="reference.md",
        content="# Reference",
        content_type="text/markdown",
    )
    pool, conn = make_pool(fetchrow=ref_row)
    store = PostgresSkillStore(pool)

    result = await store.get_reference_file(skill_id, "reference.md")

    assert result is not None
    assert result.filename == "reference.md"
    assert result.content == "# Reference"


@pytest.mark.asyncio
async def test_get_reference_file_returns_none_when_missing():
    pool, conn = make_pool(fetchrow=None)
    store = PostgresSkillStore(pool)

    result = await store.get_reference_file(uuid4(), "does-not-exist.md")

    assert result is None


@pytest.mark.asyncio
async def test_add_reference_file():
    skill_id = uuid4()
    ref_row = dict(
        id=uuid4(),
        skill_id=skill_id,
        filename="notes.md",
        content="notes",
        content_type="text/markdown",
    )
    pool, conn = make_pool(fetchrow=ref_row)
    store = PostgresSkillStore(pool)

    file = ReferenceFile(
        filename="notes.md",
        content="notes",
        content_type="text/markdown",
        skill_id=skill_id,
    )
    result = await store.add_reference_file(file)

    assert result.filename == "notes.md"


@pytest.mark.asyncio
async def test_delete_returns_true_when_deleted():
    pool, conn = make_pool(execute="DELETE 1")
    store = PostgresSkillStore(pool)

    result = await store.delete(uuid4())

    assert result is True


@pytest.mark.asyncio
async def test_delete_returns_false_when_nothing_deleted():
    pool, conn = make_pool(execute="DELETE 0")
    store = PostgresSkillStore(pool)

    result = await store.delete(uuid4())

    assert result is False
