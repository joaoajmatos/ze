"""Screen resolvers for workspace runs and the files placed this turn (phase 195)."""

from __future__ import annotations

from typing import Any

from ze_agents.screen import (
    ResolveContext,
    ScreenLine,
    ScreenPosture,
    ScreenRef,
    ScreenResolver,
    as_utc,
    parse_uuid,
    resolve_each,
    sanitize_text,
    time_ago,
)

MAX_PLACED_SHOWN = 5


class WorkspaceRunScreenResolver:
    kinds = frozenset({"workspace_run"})

    def __init__(self, workspace_store: Any) -> None:
        self._store = workspace_store

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        return await resolve_each(refs, lambda ref: self._load(ref, ctx))

    async def _load(self, ref: ScreenRef, ctx: ResolveContext) -> ScreenLine | None:
        run_id = parse_uuid(ref.id)
        run = await self._store.get_run(run_id) if run_id else None
        if run is None:
            return None
        status = str(getattr(run.status, "value", run.status) or "running").replace(
            "_", " "
        )
        parts = [status]
        if run.started_at:
            parts.append(f"started {time_ago(as_utc(run.started_at), ctx.now)}")
        if run.exit_code is not None:
            parts.append(f"exit {run.exit_code}")
        command = sanitize_text(run.command, 60)
        return ScreenLine(
            ref=ref,
            label=command,
            summary=", ".join(parts),
            posture=ScreenPosture(
                source="workspace", updated_at=as_utc(run.ended_at or run.started_at)
            ),
        )


class WorkspacePlacedScreenResolver:
    """The files the user placed this turn; the client sends them in `workspace_placed`, not as refs."""

    kinds = frozenset({"workspace_placed"})

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        shown = ctx.placed[:MAX_PLACED_SHOWN]
        files = ", ".join(
            f"{sanitize_text(p.path, 60)}"
            + (f" ({p.size} bytes)" if p.size is not None else "")
            for p in shown
        )
        more = (
            f" and {len(ctx.placed) - len(shown)} more"
            if len(ctx.placed) > len(shown)
            else ""
        )
        summary = (
            "the user placed these files in the workspace this turn "
            f"(not ingested unless you call ingest_workspace_file): {files}{more}"
        )
        return [
            ScreenLine(ref=ref, label="files placed this turn", summary=summary)
            for ref in refs
        ]


def build_screen_resolvers(*, workspace_store: Any) -> list[ScreenResolver]:
    return [
        WorkspaceRunScreenResolver(workspace_store),
        WorkspacePlacedScreenResolver(),
    ]
