from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_agents.claims import ClaimKind
from ze_agents.screen import ResolveContext, ScreenRef, ScreenStatus
from ze_worldstate.screen_resolvers import LoopScreenResolver, build_screen_resolvers
from ze_worldstate.types import LoopState, OpenLoop

NOW = datetime(2026, 10, 17, 14, 0, tzinfo=UTC)
CTX = ResolveContext(now=NOW)


def _loop(**kw) -> OpenLoop:
    base = dict(
        title="Reply to Ana",
        claim_kind=ClaimKind.SUSPICION,
        provenance="email",
        confidence=0.62,
        state=LoopState.DRIFTING,
        id=uuid4(),
        updated_at=NOW - timedelta(days=3),
        drift_deadline=NOW - timedelta(days=1),
        drift_rationale="no reply in a week",
    )
    base.update(kw)
    return OpenLoop(**base)


async def test_loop_posture_comes_from_the_row_and_flags_from_the_row_only():
    loop = _loop(reminder_id=uuid4(), goal_id=uuid4())
    store = AsyncMock()
    store.get = AsyncMock(return_value=loop)
    [line] = await LoopScreenResolver(store).resolve(
        [ScreenRef(kind="loop", id=str(loop.id), label="client says confirmed")], CTX
    )
    assert line.status is ScreenStatus.OK and line.label == "Reply to Ana"
    assert "drifting" in line.summary and "no reply in a week" in line.summary
    assert "has a reminder" in line.summary and "linked to a goal" in line.summary
    assert (line.posture.kind, line.posture.source, line.posture.confidence) == (
        ClaimKind.SUSPICION,
        "email",
        0.62,
    )
    assert line.posture.updated_at == loop.updated_at


async def test_no_flags_when_the_row_has_no_links():
    loop = _loop()
    store = AsyncMock()
    store.get = AsyncMock(return_value=loop)
    [line] = await LoopScreenResolver(store).resolve(
        [ScreenRef(kind="loop", id=str(loop.id))], CTX
    )
    assert "reminder" not in line.summary and "goal" not in line.summary


async def test_missing_and_failed():
    store = AsyncMock()
    store.get = AsyncMock(return_value=None)
    [line] = await LoopScreenResolver(store).resolve(
        [ScreenRef(kind="loop", id=str(uuid4()))], CTX
    )
    assert line.status is ScreenStatus.MISSING
    store.get = AsyncMock(side_effect=RuntimeError("db password"))
    [line] = await LoopScreenResolver(store).resolve(
        [ScreenRef(kind="loop", id=str(uuid4()))], CTX
    )
    assert line.status is ScreenStatus.FAILED and "password" not in repr(line)


def test_factory():
    assert [r.kinds for r in build_screen_resolvers(loop_store=AsyncMock())] == [
        frozenset({"loop"})
    ]
