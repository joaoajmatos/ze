from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_agents.claims import ClaimKind
from ze_agents.screen import ResolveContext, ScreenRef, ScreenStatus
from ze_correlation.screen_resolvers import HypothesisScreenResolver

CTX = ResolveContext(now=datetime(2026, 10, 17, tzinfo=UTC))


async def test_hypothesis_posture_is_read_from_the_record():
    hid = uuid4()
    hyp = SimpleNamespace(
        id=hid,
        summary="Ana and Project X may be linked",
        relation="causal_guess",
        confidence=0.4,
        evidence=[1, 2],
        claim_kind=ClaimKind.SUSPICION,
        confirmed=False,
        created_at=datetime(2026, 10, 10, tzinfo=UTC),
    )
    store = AsyncMock()
    store.get = AsyncMock(return_value=hyp)
    [line] = await HypothesisScreenResolver(store).resolve(
        [ScreenRef(kind="hypothesis", id=str(hid))], CTX
    )
    assert line.summary == "causal guess, 2 pieces of evidence"
    assert (line.posture.kind, line.posture.confidence) == (ClaimKind.SUSPICION, 0.4)
    store.get = AsyncMock(return_value=None)
    [gone] = await HypothesisScreenResolver(store).resolve(
        [ScreenRef(kind="hypothesis", id=str(hid))], CTX
    )
    assert gone.status is ScreenStatus.MISSING
