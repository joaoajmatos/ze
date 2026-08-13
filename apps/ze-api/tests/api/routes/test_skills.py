"""REST route tests for /api/v0/skills (Phase 114, User Story 1)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_api.api.dependencies import require_api_key
from ze_api.api.routes.skills import router
from ze_skills.errors import SkillParseError
from ze_skills.importer import FetchedReferenceFile, FetchedSkill
from ze_skills.parser import ParsedSkill
from ze_skills.types import Skill, SkillReview, SkillSource, SkillStatus

API_KEY = "test-key"


def _skill(**overrides) -> Skill:
    defaults = dict(
        id=uuid4(),
        name="Pirate Speak",
        description='Ends every response with "Arrr!"',
        instructions='Always end with "Arrr!"',
        source=SkillSource.IMPORTED,
        origin_url="http://example.com/SKILL.md",
        status=SkillStatus.PENDING_REVIEW,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Skill(**defaults)


def _make_app(store=None) -> tuple[FastAPI, AsyncMock]:
    app = FastAPI()
    skill_store = store or AsyncMock()
    container = SimpleNamespace(skill_store=skill_store)
    app.state.container = container

    app.dependency_overrides[require_api_key] = lambda: None
    app.include_router(router, prefix="/api/v0")
    return app, skill_store


def _default_store_mocks(store: AsyncMock) -> None:
    store.list_reference_files = AsyncMock(return_value=[])
    store.get_latest_review = AsyncMock(return_value=None)


@pytest.mark.asyncio
async def test_import_skill_success_returns_201():
    store = AsyncMock()
    created = _skill()
    store.create = AsyncMock(return_value=created)
    store.add_reference_file = AsyncMock()
    _default_store_mocks(store)
    app, _ = _make_app(store)

    fetched = FetchedSkill(
        parsed=ParsedSkill(
            name="Pirate Speak",
            description='Ends every response with "Arrr!"',
            instructions='Always end with "Arrr!"',
            allowed_tools=None,
            has_unsupported_scripts=False,
        ),
        reference_files=[],
    )

    with patch("ze_skills.rest.fetch_skill_source", AsyncMock(return_value=fetched)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v0/skills/import",
                json={"url": "http://example.com/SKILL.md"},
                headers={"Authorization": f"Bearer {API_KEY}"},
            )

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Pirate Speak"
    assert data["status"] == "pending_review"
    assert data["instructions"]
    store.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_skill_with_reference_files_persists_them():
    store = AsyncMock()
    created = _skill()
    store.create = AsyncMock(return_value=created)
    store.add_reference_file = AsyncMock()
    _default_store_mocks(store)
    app, _ = _make_app(store)

    fetched = FetchedSkill(
        parsed=ParsedSkill(
            name="Pirate Speak",
            description="desc",
            instructions="instructions",
            allowed_tools=None,
            has_unsupported_scripts=False,
        ),
        reference_files=[
            FetchedReferenceFile(
                filename="reference.md", content="# Ref", content_type="text/markdown"
            )
        ],
    )

    with patch("ze_skills.rest.fetch_skill_source", AsyncMock(return_value=fetched)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v0/skills/import",
                json={"url": "http://example.com/skill.zip"},
                headers={"Authorization": f"Bearer {API_KEY}"},
            )

    assert resp.status_code == 201
    store.add_reference_file.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_skill_parse_failure_returns_422_and_creates_no_row():
    store = AsyncMock()
    store.create = AsyncMock()
    app, _ = _make_app(store)

    with patch(
        "ze_skills.rest.fetch_skill_source",
        AsyncMock(side_effect=SkillParseError("unreachable")),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v0/skills/import",
                json={"url": "http://example.com/does-not-exist.md"},
                headers={"Authorization": f"Bearer {API_KEY}"},
            )

    assert resp.status_code == 422
    store.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_approve_skill_success():
    skill_id = uuid4()
    pending = _skill(id=skill_id, status=SkillStatus.PENDING_REVIEW)
    active = _skill(id=skill_id, status=SkillStatus.ACTIVE)
    store = AsyncMock()
    store.get = AsyncMock(return_value=pending)
    store.transition = AsyncMock(return_value=active)
    store.add_review = AsyncMock()
    _default_store_mocks(store)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/skills/{skill_id}/approve",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_approve_skill_409_when_not_pending():
    skill_id = uuid4()
    already_active = _skill(id=skill_id, status=SkillStatus.ACTIVE)
    store = AsyncMock()
    store.get = AsyncMock(return_value=already_active)
    store.transition = AsyncMock(return_value=None)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/skills/{skill_id}/approve",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_approve_skill_404_when_missing():
    store = AsyncMock()
    store.get = AsyncMock(return_value=None)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/skills/{uuid4()}/approve",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reject_skill_success():
    skill_id = uuid4()
    pending = _skill(id=skill_id, status=SkillStatus.PENDING_REVIEW)
    rejected = _skill(id=skill_id, status=SkillStatus.REJECTED)
    store = AsyncMock()
    store.get = AsyncMock(return_value=pending)
    store.transition = AsyncMock(return_value=rejected)
    store.add_review = AsyncMock()
    _default_store_mocks(store)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/skills/{skill_id}/reject",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_get_skill_detail_returns_full_content():
    skill = _skill()
    store = AsyncMock()
    store.get = AsyncMock(return_value=skill)
    _default_store_mocks(store)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/skills/{skill.id}",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["instructions"] == skill.instructions
    assert data["reference_files"] == []
    assert data["previous_version"] is None


@pytest.mark.asyncio
async def test_get_skill_detail_includes_previous_version_when_pending_reapproval():
    skill = _skill(status=SkillStatus.PENDING_REVIEW)
    store = AsyncMock()
    store.get = AsyncMock(return_value=skill)
    store.list_reference_files = AsyncMock(return_value=[])
    prior_review = SkillReview(
        id=uuid4(),
        skill_id=skill.id,
        content_snapshot={"name": "Old Name", "description": "old desc"},
        decision="approved",
        decided_at=datetime.now(timezone.utc),
    )
    store.get_latest_review = AsyncMock(return_value=prior_review)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/skills/{skill.id}",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    assert resp.json()["previous_version"]["name"] == "Old Name"


@pytest.mark.asyncio
async def test_get_skill_404_when_missing():
    store = AsyncMock()
    store.get = AsyncMock(return_value=None)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/skills/{uuid4()}",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_skills_returns_wrapped_list():
    store = AsyncMock()
    store.list = AsyncMock(return_value=[_skill(), _skill()])
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/skills", headers={"Authorization": f"Bearer {API_KEY}"}
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["skills"]) == 2


@pytest.mark.asyncio
async def test_list_skills_filters_by_status_and_source():
    store = AsyncMock()
    store.list = AsyncMock(return_value=[])
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/skills?status=active&source=imported",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    store.list.assert_awaited_once_with(
        status=SkillStatus.ACTIVE, source=SkillSource.IMPORTED
    )


@pytest.mark.asyncio
async def test_get_reference_file_content_200():
    skill = _skill()
    store = AsyncMock()
    store.get = AsyncMock(return_value=skill)
    store.get_reference_file = AsyncMock(
        return_value=SimpleNamespace(
            filename="reference.md",
            content="# Reference content",
            content_type="text/markdown",
        )
    )
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/skills/{skill.id}/reference-files/reference.md",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "# Reference content"


@pytest.mark.asyncio
async def test_get_reference_file_404_for_unknown_filename():
    skill = _skill()
    store = AsyncMock()
    store.get = AsyncMock(return_value=skill)
    store.get_reference_file = AsyncMock(return_value=None)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/skills/{skill.id}/reference-files/does-not-exist.md",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_reference_file_404_when_skill_missing():
    store = AsyncMock()
    store.get = AsyncMock(return_value=None)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/skills/{uuid4()}/reference-files/reference.md",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_disable_skill_success():
    skill_id = uuid4()
    active = _skill(id=skill_id, status=SkillStatus.ACTIVE)
    disabled = _skill(id=skill_id, status=SkillStatus.DISABLED)
    store = AsyncMock()
    store.get = AsyncMock(return_value=active)
    store.transition = AsyncMock(return_value=disabled)
    _default_store_mocks(store)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/skills/{skill_id}/disable",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"


@pytest.mark.asyncio
async def test_disable_skill_409_when_not_active():
    skill_id = uuid4()
    pending = _skill(id=skill_id, status=SkillStatus.PENDING_REVIEW)
    store = AsyncMock()
    store.get = AsyncMock(return_value=pending)
    store.transition = AsyncMock(return_value=None)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/skills/{skill_id}/disable",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_enable_skill_success():
    skill_id = uuid4()
    disabled = _skill(id=skill_id, status=SkillStatus.DISABLED)
    active = _skill(id=skill_id, status=SkillStatus.ACTIVE)
    store = AsyncMock()
    store.get = AsyncMock(return_value=disabled)
    store.transition = AsyncMock(return_value=active)
    _default_store_mocks(store)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/skills/{skill_id}/enable",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_enable_skill_409_when_not_disabled():
    skill_id = uuid4()
    drifted = _skill(id=skill_id, status=SkillStatus.PENDING_REVIEW)
    store = AsyncMock()
    store.get = AsyncMock(return_value=drifted)
    store.transition = AsyncMock(return_value=None)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/skills/{skill_id}/enable",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_skill_success_returns_204():
    skill_id = uuid4()
    imported = _skill(id=skill_id, source=SkillSource.IMPORTED)
    store = AsyncMock()
    store.get = AsyncMock(return_value=imported)
    store.delete = AsyncMock(return_value=True)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete(
            f"/api/v0/skills/{skill_id}",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 204
    store.delete.assert_awaited_once_with(skill_id)


@pytest.mark.asyncio
async def test_delete_skill_422_when_bundled():
    skill_id = uuid4()
    bundled = _skill(id=skill_id, source=SkillSource.BUNDLED, status=SkillStatus.ACTIVE)
    store = AsyncMock()
    store.get = AsyncMock(return_value=bundled)
    store.delete = AsyncMock()
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete(
            f"/api/v0/skills/{skill_id}",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 422
    store.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_skill_404_when_missing():
    store = AsyncMock()
    store.get = AsyncMock(return_value=None)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete(
            f"/api/v0/skills/{uuid4()}",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 404
