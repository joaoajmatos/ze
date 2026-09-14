from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from ze_logging import get_logger
from ze_sdk import DBPool

from ze_skills.types import ReferenceFile, Skill, SkillReview, SkillScript, SkillSource, SkillStatus

log = get_logger(__name__)


def _skill_from_row(row) -> Skill:
    return Skill(
        id=row["id"],
        name=row["name"],
        slug=row["slug"],
        description=row["description"],
        instructions=row["instructions"],
        source=SkillSource(row["source"]),
        origin_url=row["origin_url"],
        bundling_plugin=row["bundling_plugin"],
        status=SkillStatus(row["status"]),
        allowed_tools=row["allowed_tools"],
        has_scripts=bool(row["has_scripts"]),
        executable_approved=bool(row["executable_approved"]),
        executable_approved_at=row["executable_approved_at"],
        content_hash=row["content_hash"],
        created_at=row["created_at"],
        approved_at=row["approved_at"],
        last_checked_at=row["last_checked_at"],
        last_check_error=row["last_check_error"],
    )


def _reference_file_from_row(row) -> ReferenceFile:
    return ReferenceFile(
        id=row["id"],
        skill_id=row["skill_id"],
        filename=row["filename"],
        content=row["content"],
        content_type=row["content_type"],
    )


def _review_from_row(row) -> SkillReview:
    return SkillReview(
        id=row["id"],
        skill_id=row["skill_id"],
        content_snapshot=row["content_snapshot"],
        decision=row["decision"],
        decided_at=row["decided_at"],
    )


class SkillStore(Protocol):
    async def create(self, skill: Skill) -> Skill: ...

    async def get(self, skill_id: UUID) -> Skill | None: ...

    async def get_by_slug_source(
        self, slug: str, source: SkillSource
    ) -> Skill | None: ...

    async def list(
        self,
        status: SkillStatus | None = None,
        source: SkillSource | None = None,
    ) -> list[Skill]: ...

    async def list_active(self) -> list[Skill]: ...

    async def transition(
        self,
        skill_id: UUID,
        expected_status: SkillStatus,
        new_status: SkillStatus,
        *,
        set_approved_at: bool = False,
    ) -> Skill | None: ...

    async def delete(self, skill_id: UUID) -> bool: ...

    async def mark_checked(
        self, skill_id: UUID, *, error: str | None
    ) -> Skill | None: ...

    async def apply_content_change(
        self,
        skill_id: UUID,
        *,
        name: str,
        description: str,
        instructions: str,
        allowed_tools: list[str] | None,
        has_scripts: bool,
        content_hash: str,
        new_status: SkillStatus,
    ) -> Skill | None: ...

    async def set_executable_approved(
        self, skill_id: UUID, *, approved: bool
    ) -> Skill | None: ...

    async def add_reference_file(self, file: ReferenceFile) -> ReferenceFile: ...

    async def delete_reference_files(self, skill_id: UUID) -> None: ...

    async def list_reference_files(self, skill_id: UUID) -> list[ReferenceFile]: ...

    async def get_reference_file(
        self, skill_id: UUID, filename: str
    ) -> ReferenceFile | None: ...

    async def add_script(self, script: SkillScript) -> SkillScript: ...

    async def delete_scripts(self, skill_id: UUID) -> None: ...

    async def list_scripts(self, skill_id: UUID) -> list[SkillScript]: ...

    async def get_script(
        self, skill_id: UUID, filename: str
    ) -> SkillScript | None: ...

    async def add_review(self, review: SkillReview) -> SkillReview: ...

    async def delete_reference_files(self, skill_id: UUID) -> None: ...

    async def list_reference_files(self, skill_id: UUID) -> list[ReferenceFile]: ...

    async def get_reference_file(
        self, skill_id: UUID, filename: str
    ) -> ReferenceFile | None: ...

    async def add_review(self, review: SkillReview) -> SkillReview: ...

    async def get_latest_review(
        self, skill_id: UUID, decision: str | None = None
    ) -> SkillReview | None: ...


class PostgresSkillStore:
    def __init__(self, pool: DBPool) -> None:
        self._pool = pool

    async def create(self, skill: Skill) -> Skill:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO skills
                  (name, slug, description, instructions, source, origin_url,
                   bundling_plugin, status, allowed_tools, has_scripts,
                   content_hash)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING *
                """,
                skill.name,
                skill.slug,
                skill.description,
                skill.instructions,
                skill.source.value,
                skill.origin_url,
                skill.bundling_plugin,
                skill.status.value,
                skill.allowed_tools,
                skill.has_scripts,
                skill.content_hash,
            )
        result = _skill_from_row(row)
        log.info(
            "skill_created",
            skill_id=str(result.id),
            source=result.source.value,
            status=result.status.value,
        )
        return result

    async def get(self, skill_id: UUID) -> Skill | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM skills WHERE id = $1", skill_id)
        return _skill_from_row(row) if row else None

    async def get_by_slug_source(self, slug: str, source: SkillSource) -> Skill | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM skills WHERE slug = $1 AND source = $2",
                slug,
                source.value,
            )
        return _skill_from_row(row) if row else None

    async def list(
        self,
        status: SkillStatus | None = None,
        source: SkillSource | None = None,
    ) -> list[Skill]:
        conditions: list[str] = []
        params: list = []
        if status is not None:
            params.append(status.value)
            conditions.append(f"status = ${len(params)}")
        if source is not None:
            params.append(source.value)
            conditions.append(f"source = ${len(params)}")
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM skills{where} ORDER BY created_at DESC", *params
            )
        return [_skill_from_row(r) for r in rows]

    async def list_active(self) -> list[Skill]:
        return await self.list(status=SkillStatus.ACTIVE)

    async def transition(
        self,
        skill_id: UUID,
        expected_status: SkillStatus,
        new_status: SkillStatus,
        *,
        set_approved_at: bool = False,
    ) -> Skill | None:
        approved_at = datetime.now(timezone.utc) if set_approved_at else None
        async with self._pool.acquire() as conn:
            if set_approved_at:
                row = await conn.fetchrow(
                    """
                    UPDATE skills
                    SET status = $3, approved_at = $4
                    WHERE id = $1 AND status = $2
                    RETURNING *
                    """,
                    skill_id,
                    expected_status.value,
                    new_status.value,
                    approved_at,
                )
            else:
                row = await conn.fetchrow(
                    """
                    UPDATE skills
                    SET status = $3
                    WHERE id = $1 AND status = $2
                    RETURNING *
                    """,
                    skill_id,
                    expected_status.value,
                    new_status.value,
                )
        if row is None:
            return None
        result = _skill_from_row(row)
        log.info(
            "skill_transitioned",
            skill_id=str(skill_id),
            from_status=expected_status.value,
            to_status=new_status.value,
        )
        return result

    async def delete(self, skill_id: UUID) -> bool:
        async with self._pool.acquire() as conn:
            result = await conn.execute("DELETE FROM skills WHERE id = $1", skill_id)
        deleted = result != "DELETE 0"
        if deleted:
            log.info("skill_deleted", skill_id=str(skill_id))
        return deleted

    async def mark_checked(self, skill_id: UUID, *, error: str | None) -> Skill | None:
        """Update `last_checked_at`/`last_check_error` without touching `status` —
        used for the unchanged-content and unreachable-source recheck branches."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE skills
                SET last_checked_at = now(), last_check_error = $2
                WHERE id = $1
                RETURNING *
                """,
                skill_id,
                error,
            )
        return _skill_from_row(row) if row else None

    async def apply_content_change(
        self,
        skill_id: UUID,
        *,
        name: str,
        description: str,
        instructions: str,
        allowed_tools: list[str] | None,
        has_scripts: bool,
        content_hash: str,
        new_status: SkillStatus,
    ) -> Skill | None:
        """Persist a recheck-detected content change: overwrite the content
        fields, revert `status` to `new_status`, clear executable approval,
        and stamp `last_checked_at` (FR-015)."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE skills
                SET name = $2, description = $3, instructions = $4,
                    allowed_tools = $5, has_scripts = $6,
                    content_hash = $7, status = $8,
                    executable_approved = false,
                    executable_approved_at = NULL,
                    last_checked_at = now(), last_check_error = NULL
                WHERE id = $1
                RETURNING *
                """,
                skill_id,
                name,
                description,
                instructions,
                allowed_tools,
                has_scripts,
                content_hash,
                new_status.value,
            )
        result = _skill_from_row(row) if row else None
        if result is not None:
            log.info("skill_content_changed", skill_id=str(skill_id))
        return result

    async def add_reference_file(self, file: ReferenceFile) -> ReferenceFile:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO skill_reference_files
                  (skill_id, filename, content, content_type)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                file.skill_id,
                file.filename,
                file.content,
                file.content_type,
            )
        return _reference_file_from_row(row)

    async def delete_reference_files(self, skill_id: UUID) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM skill_reference_files WHERE skill_id = $1", skill_id
            )

    async def list_reference_files(self, skill_id: UUID) -> list[ReferenceFile]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM skill_reference_files WHERE skill_id = $1"
                " ORDER BY filename",
                skill_id,
            )
        return [_reference_file_from_row(r) for r in rows]

    async def get_reference_file(
        self, skill_id: UUID, filename: str
    ) -> ReferenceFile | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM skill_reference_files"
                " WHERE skill_id = $1 AND filename = $2",
                skill_id,
                filename,
            )
        return _reference_file_from_row(row) if row else None

    async def add_review(self, review: SkillReview) -> SkillReview:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO skill_reviews (skill_id, content_snapshot, decision)
                VALUES ($1, $2, $3)
                RETURNING *
                """,
                review.skill_id,
                review.content_snapshot,
                review.decision,
            )
        return _review_from_row(row)

    async def get_latest_review(
        self, skill_id: UUID, decision: str | None = None
    ) -> SkillReview | None:
        async with self._pool.acquire() as conn:
            if decision is not None:
                row = await conn.fetchrow(
                    "SELECT * FROM skill_reviews WHERE skill_id = $1 AND decision = $2"
                    " ORDER BY decided_at DESC LIMIT 1",
                    skill_id,
                    decision,
                )
            else:
                row = await conn.fetchrow(
                    "SELECT * FROM skill_reviews WHERE skill_id = $1"
                    " ORDER BY decided_at DESC LIMIT 1",
                    skill_id,
                )
        return _review_from_row(row) if row else None

    async def set_executable_approved(
        self, skill_id: UUID, *, approved: bool
    ) -> Skill | None:
        async with self._pool.acquire() as conn:
            if approved:
                row = await conn.fetchrow(
                    """
                    UPDATE skills
                    SET executable_approved = true,
                        executable_approved_at = now()
                    WHERE id = $1
                    RETURNING *
                    """,
                    skill_id,
                )
            else:
                row = await conn.fetchrow(
                    """
                    UPDATE skills
                    SET executable_approved = false,
                        executable_approved_at = NULL
                    WHERE id = $1
                    RETURNING *
                    """,
                    skill_id,
                )
        return _skill_from_row(row) if row else None

    def _script_from_row(self, row) -> SkillScript:
        return SkillScript(
            id=row["id"],
            skill_id=row["skill_id"],
            filename=row["filename"],
            content=bytes(row["content"]) if row["content"] is not None else b"",
        )

    async def add_script(self, script: SkillScript) -> SkillScript:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO skill_scripts (skill_id, filename, content)
                VALUES ($1, $2, $3)
                ON CONFLICT (skill_id, filename) DO UPDATE
                  SET content = EXCLUDED.content
                RETURNING *
                """,
                script.skill_id,
                script.filename,
                script.content,
            )
        return self._script_from_row(row)

    async def delete_scripts(self, skill_id: UUID) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM skill_scripts WHERE skill_id = $1", skill_id
            )

    async def list_scripts(self, skill_id: UUID) -> list[SkillScript]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM skill_scripts WHERE skill_id = $1 ORDER BY filename",
                skill_id,
            )
        return [self._script_from_row(r) for r in rows]

    async def get_script(
        self, skill_id: UUID, filename: str
    ) -> SkillScript | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM skill_scripts WHERE skill_id = $1 AND filename = $2",
                skill_id,
                filename,
            )
        return self._script_from_row(row) if row else None

