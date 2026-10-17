from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_agents.screen import ResolveContext, ScreenRef, ScreenStatus, WorkspacePlaced
from ze_workspace.screen_resolvers import (
    WorkspacePlacedScreenResolver,
    WorkspaceRunScreenResolver,
)
from ze_workspace.types import WorkspaceRun, WorkspaceRunOrigin, WorkspaceRunStatus

NOW = datetime(2026, 10, 17, 14, 0, tzinfo=UTC)


async def test_run_line_summarises_command_status_and_exit():
    rid = uuid4()
    run = WorkspaceRun(
        command="python build.py\n--all",
        origin=next(iter(WorkspaceRunOrigin)),
        status=WorkspaceRunStatus.FAILED,
        id=rid,
        started_at=NOW - timedelta(hours=2),
        exit_code=2,
    )
    store = AsyncMock()
    store.get_run = AsyncMock(return_value=run)
    [line] = await WorkspaceRunScreenResolver(store).resolve(
        [ScreenRef(kind="workspace_run", id=str(rid))], ResolveContext(now=NOW)
    )
    assert line.label == "python build.py --all"
    assert line.summary == "failed, started 2 h ago, exit 2"
    store.get_run = AsyncMock(return_value=None)
    [gone] = await WorkspaceRunScreenResolver(store).resolve(
        [ScreenRef(kind="workspace_run", id=str(rid))], ResolveContext(now=NOW)
    )
    assert gone.status is ScreenStatus.MISSING


async def test_placed_files_text_keeps_the_ingest_warning_and_caps_the_list():
    placed = tuple(WorkspacePlaced(path=f"f{i}.txt", size=i) for i in range(7))
    [line] = await WorkspacePlacedScreenResolver().resolve(
        [ScreenRef(kind="workspace_placed", id="placed")],
        ResolveContext(now=NOW, placed=placed),
    )
    assert "not ingested unless you call ingest_workspace_file" in line.summary
    assert (
        "f0.txt (0 bytes)" in line.summary
        and "f4.txt" in line.summary
        and "f5.txt" not in line.summary
    )
    assert "and 2 more" in line.summary
