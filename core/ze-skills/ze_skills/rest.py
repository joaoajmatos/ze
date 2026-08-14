from __future__ import annotations

from uuid import UUID

import httpx

from ze_skills import review
from ze_skills.errors import SkillNotFoundError
from ze_skills.importer import fetch_skill_source
from ze_skills.store import SkillStore
from ze_skills.types import ReferenceFile, Skill, SkillScript, SkillSource, SkillStatus


def _skill_to_list_item(skill: Skill) -> dict:
    return {
        "id": skill.id,
        "name": skill.name,
        "slug": skill.slug,
        "description": skill.description,
        "source": skill.source.value,
        "origin_url": skill.origin_url,
        "bundling_plugin": skill.bundling_plugin,
        "status": skill.status.value,
        "has_scripts": skill.has_scripts,
        "executable_approved": skill.executable_approved,
        "created_at": skill.created_at.isoformat() if skill.created_at else None,
        "approved_at": skill.approved_at.isoformat() if skill.approved_at else None,
        "last_checked_at": (
            skill.last_checked_at.isoformat() if skill.last_checked_at else None
        ),
        "last_check_error": skill.last_check_error,
        "script_filenames": [],
    }


async def _detail(store: SkillStore, skill: Skill) -> dict:
    reference_files = await store.list_reference_files(skill.id)
    scripts = await store.list_scripts(skill.id)
    detail = {
        **_skill_to_list_item(skill),
        "instructions": skill.instructions,
        "allowed_tools": skill.allowed_tools,
        "script_filenames": [s.filename for s in scripts],
        "reference_files": [
            {"filename": f.filename, "content_type": f.content_type}
            for f in reference_files
        ],
        "previous_version": None,
    }
    if skill.status == SkillStatus.PENDING_REVIEW:
        prior = await store.get_latest_review(skill.id, decision="approved")
        if prior is not None:
            detail["previous_version"] = prior.content_snapshot
    return detail


async def import_skill(
    store: SkillStore, url: str, http_client: httpx.AsyncClient | None = None
) -> dict:
    """Fetch and parse `url`, persist a new pending-review `Skill` row plus any
    supporting reference files. Never activates it (FR-004)."""
    fetched = await fetch_skill_source(url, client=http_client)
    parsed = fetched.parsed

    skill = Skill(
        name=parsed.name,
        description=parsed.description,
        instructions=parsed.instructions,
        source=SkillSource.IMPORTED,
        origin_url=url,
        allowed_tools=parsed.allowed_tools,
        has_scripts=parsed.has_scripts,
        status=SkillStatus.PENDING_REVIEW,
    )
    created = await store.create(skill)

    for ref in fetched.reference_files:
        await store.add_reference_file(
            ReferenceFile(
                skill_id=created.id,
                filename=ref.filename,
                content=ref.content,
                content_type=ref.content_type,
            )
        )
    for script in fetched.script_files:
        await store.add_script(
            SkillScript(
                skill_id=created.id,
                filename=script.filename,
                content=script.content,
            )
        )

    return await _detail(store, created)


async def get_skill(store: SkillStore, skill_id: UUID) -> dict:
    skill = await store.get(skill_id)
    if skill is None:
        raise SkillNotFoundError(f"Skill {skill_id} not found")
    return await _detail(store, skill)


async def list_skills(
    store: SkillStore,
    status: SkillStatus | None = None,
    source: SkillSource | None = None,
) -> list[dict]:
    skills = await store.list(status=status, source=source)
    items = []
    for s in skills:
        item = _skill_to_list_item(s)
        scripts = await store.list_scripts(s.id) if s.id else []
        item["script_filenames"] = [x.filename for x in scripts]
        items.append(item)
    return items


async def get_reference_file(store: SkillStore, skill_id: UUID, filename: str) -> dict:
    skill = await store.get(skill_id)
    if skill is None:
        raise SkillNotFoundError(f"Skill {skill_id} not found")
    ref = await store.get_reference_file(skill_id, filename)
    if ref is None:
        raise SkillNotFoundError(
            f"Reference file {filename!r} not found on skill {skill_id}"
        )
    return {
        "filename": ref.filename,
        "content_type": ref.content_type,
        "content": ref.content,
    }


async def approve(store: SkillStore, skill_id: UUID) -> dict:
    skill = await review.approve_skill(store, skill_id)
    return await _detail(store, skill)


async def approve_executables(store: SkillStore, skill_id: UUID) -> dict:
    skill = await review.approve_skill_executables(store, skill_id)
    return await _detail(store, skill)


async def reject(store: SkillStore, skill_id: UUID) -> dict:
    skill = await review.reject_skill(store, skill_id)
    return await _detail(store, skill)


async def disable(store: SkillStore, skill_id: UUID) -> dict:
    skill = await review.disable_skill(store, skill_id)
    return await _detail(store, skill)


async def enable(store: SkillStore, skill_id: UUID) -> dict:
    skill = await review.enable_skill(store, skill_id)
    return await _detail(store, skill)


async def remove(store: SkillStore, skill_id: UUID) -> None:
    await review.remove_skill(store, skill_id)


async def refresh(
    store: SkillStore, skill_id: UUID, http_client: httpx.AsyncClient | None = None
) -> dict:
    skill = await review.refresh_skill(store, skill_id, http_client=http_client)
    return await _detail(store, skill)
