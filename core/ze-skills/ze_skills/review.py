from __future__ import annotations

from uuid import UUID

import httpx

from ze_logging import get_logger

from ze_skills.errors import (
    InvalidSkillTransitionError,
    SkillNotFoundError,
    SkillParseError,
)
from ze_skills.importer import fetch_skill_source
from ze_skills.store import SkillStore
from ze_skills.types import (
    ReferenceFile,
    Skill,
    SkillReview,
    SkillScript,
    SkillSource,
    SkillStatus,
    compute_content_hash,
)

log = get_logger(__name__)


def _content_snapshot(skill: Skill) -> dict:
    return {
        "name": skill.name,
        "description": skill.description,
        "instructions": skill.instructions,
        "allowed_tools": skill.allowed_tools,
        "content_hash": skill.content_hash,
        "has_scripts": skill.has_scripts,
        "script_filenames": [],
    }


async def approve_skill(store: SkillStore, skill_id: UUID) -> Skill:
    """Transition `pending_review -> active` (FR-006). Records a `SkillReview`
    row (`decision = approved`) with the current content snapshot (FR-016)."""
    skill = await store.get(skill_id)
    if skill is None:
        raise SkillNotFoundError(f"Skill {skill_id} not found")

    updated = await store.transition(
        skill_id, SkillStatus.PENDING_REVIEW, SkillStatus.ACTIVE, set_approved_at=True
    )
    if updated is None:
        raise InvalidSkillTransitionError(
            f"Cannot approve skill {skill_id}: not currently pending_review"
            f" (current status: {skill.status.value})"
        )

    await store.add_review(
        SkillReview(
            skill_id=skill_id,
            content_snapshot=_content_snapshot(skill),
            decision="approved",
        )
    )
    log.info("skill_approved", skill_id=str(skill_id))
    return updated


async def approve_skill_executables(store: SkillStore, skill_id: UUID) -> Skill:
    """Separate from instructions approval (FR-012). Requires `active` + `has_scripts`."""
    skill = await store.get(skill_id)
    if skill is None:
        raise SkillNotFoundError(f"Skill {skill_id} not found")
    if skill.status is not SkillStatus.ACTIVE:
        raise InvalidSkillTransitionError(
            f"Cannot approve executables for skill {skill_id}: "
            f"status is {skill.status.value}, expected active"
        )
    if not skill.has_scripts:
        raise InvalidSkillTransitionError(
            f"Cannot approve executables for skill {skill_id}: it has no scripts"
        )
    updated = await store.set_executable_approved(skill_id, approved=True)
    if updated is None:
        raise SkillNotFoundError(f"Skill {skill_id} not found")
    log.info("skill_executables_approved", skill_id=str(skill_id))
    return updated


async def reject_skill(store: SkillStore, skill_id: UUID) -> Skill:
    """Transition `pending_review -> rejected` (FR-006). Records a
    `SkillReview` row (`decision = rejected`)."""
    skill = await store.get(skill_id)
    if skill is None:
        raise SkillNotFoundError(f"Skill {skill_id} not found")

    updated = await store.transition(
        skill_id, SkillStatus.PENDING_REVIEW, SkillStatus.REJECTED
    )
    if updated is None:
        raise InvalidSkillTransitionError(
            f"Cannot reject skill {skill_id}: not currently pending_review"
            f" (current status: {skill.status.value})"
        )

    await store.add_review(
        SkillReview(
            skill_id=skill_id,
            content_snapshot=_content_snapshot(skill),
            decision="rejected",
        )
    )
    log.info("skill_rejected", skill_id=str(skill_id))
    return updated


async def disable_skill(store: SkillStore, skill_id: UUID) -> Skill:
    """Transition `active -> disabled` (FR-013). No new `SkillReview` row —
    disable/enable is not a content-review decision."""
    skill = await store.get(skill_id)
    if skill is None:
        raise SkillNotFoundError(f"Skill {skill_id} not found")

    updated = await store.transition(skill_id, SkillStatus.ACTIVE, SkillStatus.DISABLED)
    if updated is None:
        raise InvalidSkillTransitionError(
            f"Cannot disable skill {skill_id}: not currently active"
            f" (current status: {skill.status.value})"
        )
    log.info("skill_disabled", skill_id=str(skill_id))
    return updated


async def enable_skill(store: SkillStore, skill_id: UUID) -> Skill:
    """Transition `disabled -> active` (FR-013). No new `SkillReview` row.
    Rejected if the skill drifted to `pending_review` in the meantime (e.g. a
    content recheck reverted it) — enabling out from under a pending review
    would bypass FR-015/FR-016."""
    skill = await store.get(skill_id)
    if skill is None:
        raise SkillNotFoundError(f"Skill {skill_id} not found")

    updated = await store.transition(skill_id, SkillStatus.DISABLED, SkillStatus.ACTIVE)
    if updated is None:
        raise InvalidSkillTransitionError(
            f"Cannot enable skill {skill_id}: not currently disabled"
            f" (current status: {skill.status.value})"
        )
    log.info("skill_enabled", skill_id=str(skill_id))
    return updated


async def remove_skill(store: SkillStore, skill_id: UUID) -> None:
    """Delete a skill and its cascaded `ReferenceFile`/`SkillReview` rows
    (FR-014). Bundled skills are developer-owned and can't be removed via the
    management UI."""
    skill = await store.get(skill_id)
    if skill is None:
        raise SkillNotFoundError(f"Skill {skill_id} not found")

    if skill.source == SkillSource.BUNDLED:
        raise InvalidSkillTransitionError(
            f"Cannot remove skill {skill_id}: bundled skills are not removable"
        )

    await store.delete(skill_id)
    log.info("skill_removed", skill_id=str(skill_id))


async def refresh_skill(
    store: SkillStore, skill_id: UUID, http_client: httpx.AsyncClient | None = None
) -> Skill:
    """Re-fetch an imported skill's `origin_url` and compare content hashes
    (FR-015). On a mismatch, reverts `status` to `pending_review`, replaces
    the stored content and reference files, and preserves the prior approved
    `SkillReview` for comparison (FR-016, via `rest._detail`). On an
    unreachable source, records `last_check_error` without changing `status`
    (spec Edge Cases — a dead source doesn't deactivate a working skill).
    `last_checked_at` always updates. Raises `InvalidSkillTransitionError` for
    `source == bundled` (no `origin_url` to refresh)."""
    skill = await store.get(skill_id)
    if skill is None:
        raise SkillNotFoundError(f"Skill {skill_id} not found")

    if skill.source == SkillSource.BUNDLED:
        raise InvalidSkillTransitionError(
            f"Cannot refresh skill {skill_id}: bundled skills have no origin_url"
        )

    try:
        fetched = await fetch_skill_source(skill.origin_url, client=http_client)
    except SkillParseError as exc:
        log.info("skill_refresh_unreachable", skill_id=str(skill_id), error=str(exc))
        updated = await store.mark_checked(skill_id, error=str(exc))
        return updated if updated is not None else skill

    parsed = fetched.parsed
    new_hash = compute_content_hash(
        parsed.name, parsed.description, parsed.instructions, parsed.allowed_tools
    )
    if new_hash == skill.content_hash:
        updated = await store.mark_checked(skill_id, error=None)
        return updated if updated is not None else skill

    updated = await store.apply_content_change(
        skill_id,
        name=parsed.name,
        description=parsed.description,
        instructions=parsed.instructions,
        allowed_tools=parsed.allowed_tools,
        has_scripts=parsed.has_scripts,
        content_hash=new_hash,
        new_status=SkillStatus.PENDING_REVIEW,
    )
    if updated is None:
        raise SkillNotFoundError(f"Skill {skill_id} not found")

    await store.delete_reference_files(skill_id)
    for ref in fetched.reference_files:
        await store.add_reference_file(
            ReferenceFile(
                skill_id=skill_id,
                filename=ref.filename,
                content=ref.content,
                content_type=ref.content_type,
            )
        )
    await store.delete_scripts(skill_id)
    for script in fetched.script_files:
        await store.add_script(
            SkillScript(
                skill_id=skill_id,
                filename=script.filename,
                content=script.content,
            )
        )

    log.info("skill_content_changed_on_refresh", skill_id=str(skill_id))
    return updated
