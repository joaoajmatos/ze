from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from ze_agents.db import DBPool
from ze_logging import get_logger

from ze_workspace.errors import WorkspaceError
from ze_workspace.sanitize import redact
from ze_workspace.types import (
    WorkspaceFileTouch,
    WorkspaceMode,
    WorkspaceRun,
    WorkspaceRunOrigin,
    WorkspaceRunStatus,
    WorkspaceState,
)

log = get_logger(__name__)

_VALID_MODES = {m.value for m in WorkspaceMode}
_VALID_ORIGINS = {o.value for o in WorkspaceRunOrigin}
_VALID_STATUSES = {s.value for s in WorkspaceRunStatus}


def _parse_mode(raw: str) -> WorkspaceMode:
    if raw not in _VALID_MODES:
        raise WorkspaceError(f"unknown workspace mode: {raw!r}")
    return WorkspaceMode(raw)


def _state_from_row(row) -> WorkspaceState:
    return WorkspaceState(
        mode=_parse_mode(row["mode"]),
        last_reset_at=row["last_reset_at"],
        last_used_at=row["last_used_at"],
        updated_at=row["updated_at"],
    )


def _touches_from_json(raw) -> list[WorkspaceFileTouch]:
    if not raw:
        return []
    if isinstance(raw, str):
        raw = json.loads(raw)
    return [
        WorkspaceFileTouch(path=item["path"], op=item["op"]) for item in raw
    ]


def _run_from_row(row) -> WorkspaceRun:
    origin_raw = row["origin"]
    status_raw = row["status"]
    if origin_raw not in _VALID_ORIGINS:
        raise WorkspaceError(f"unknown workspace run origin: {origin_raw!r}")
    if status_raw not in _VALID_STATUSES:
        raise WorkspaceError(f"unknown workspace run status: {status_raw!r}")
    return WorkspaceRun(
        id=row["id"],
        command=row["command"],
        origin=WorkspaceRunOrigin(origin_raw),
        status=WorkspaceRunStatus(status_raw),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        thread_id=row["thread_id"],
        message_id=row["message_id"],
        skill_id=row["skill_id"],
        skill_script_path=row["skill_script_path"],
        exit_code=row["exit_code"],
        output_preview=row["output_preview"] or "",
        output_file_path=row["output_file_path"],
        files_touched=_touches_from_json(row["files_touched"]),
        error_summary=row["error_summary"],
    )


class WorkspaceStore(Protocol):
    async def get_state(self) -> WorkspaceState: ...

    async def get_mode(self) -> WorkspaceMode: ...

    async def set_mode(self, mode: WorkspaceMode) -> WorkspaceState: ...

    async def touch_used(self) -> None: ...

    async def mark_reset(self) -> None: ...

    async def insert_run(self, run: WorkspaceRun) -> WorkspaceRun: ...

    async def list_runs(
        self,
        *,
        limit: int = 50,
        origin: WorkspaceRunOrigin | None = None,
    ) -> list[WorkspaceRun]: ...


class PostgresWorkspaceStore:
    def __init__(self, pool: DBPool) -> None:
        self._pool = pool

    async def get_state(self) -> WorkspaceState:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM workspace_state WHERE id = 1")
            if row is None:
                row = await conn.fetchrow(
                    """
                    INSERT INTO workspace_state (id, mode)
                    VALUES (1, 'ask')
                    ON CONFLICT (id) DO UPDATE SET id = workspace_state.id
                    RETURNING *
                    """
                )
        return _state_from_row(row)

    async def get_mode(self) -> WorkspaceMode:
        state = await self.get_state()
        return state.mode

    async def set_mode(self, mode: WorkspaceMode) -> WorkspaceState:
        if mode.value not in _VALID_MODES:
            raise WorkspaceError(f"unknown workspace mode: {mode!r}")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE workspace_state
                   SET mode = $1, updated_at = now()
                 WHERE id = 1
             RETURNING *
                """,
                mode.value,
            )
            if row is None:
                row = await conn.fetchrow(
                    """
                    INSERT INTO workspace_state (id, mode, updated_at)
                    VALUES (1, $1, now())
                    RETURNING *
                    """,
                    mode.value,
                )
        log.info("workspace_mode_set", mode=mode.value)
        return _state_from_row(row)

    async def touch_used(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE workspace_state SET last_used_at = now() WHERE id = 1"
            )

    async def mark_reset(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE workspace_state
                   SET last_reset_at = now(), last_used_at = now()
                 WHERE id = 1
                """
            )

    async def insert_run(self, run: WorkspaceRun) -> WorkspaceRun:
        if not run.command:
            raise WorkspaceError("workspace run command must be non-empty")
        preview = redact(run.output_preview or "")
        error = redact(run.error_summary) if run.error_summary else None
        touches = [{"path": t.path, "op": t.op} for t in run.files_touched]
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO workspace_runs
                  (started_at, ended_at, command, origin, thread_id, message_id,
                   skill_id, skill_script_path, status, exit_code, output_preview,
                   output_file_path, files_touched, error_summary)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb, $14)
                RETURNING *
                """,
                run.started_at or now,
                run.ended_at or now,
                run.command,
                run.origin.value,
                run.thread_id,
                run.message_id,
                run.skill_id,
                run.skill_script_path,
                run.status.value,
                run.exit_code,
                preview,
                run.output_file_path,
                json.dumps(touches),
                error,
            )
        result = _run_from_row(row)
        log.info(
            "workspace_run_recorded",
            run_id=str(result.id),
            origin=result.origin.value,
            status=result.status.value,
        )
        return result

    async def list_runs(
        self,
        *,
        limit: int = 50,
        origin: WorkspaceRunOrigin | None = None,
    ) -> list[WorkspaceRun]:
        async with self._pool.acquire() as conn:
            if origin is not None:
                rows = await conn.fetch(
                    """
                    SELECT * FROM workspace_runs
                     WHERE origin = $1
                     ORDER BY started_at DESC
                     LIMIT $2
                    """,
                    origin.value,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM workspace_runs
                     ORDER BY started_at DESC
                     LIMIT $1
                    """,
                    limit,
                )
        return [_run_from_row(r) for r in rows]
