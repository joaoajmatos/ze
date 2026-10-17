from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_agents.claims import ClaimKind
from ze_personal.contacts.screen_resolvers import ContactScreenResolver
from ze_personal.contacts.types import Person
from ze_sdk.screen import ResolveContext, ScreenRef, ScreenStatus

NOW = datetime(2026, 10, 17, 14, 0, tzinfo=UTC)


async def test_contact_line_posture_comes_from_the_record():
    pid = uuid4()
    person = Person(
        name="Ana Costa",
        classification="professional",
        relationship_to_user="client",
        confirmed=False,
        confidence=0.6,
        claim_kind=ClaimKind.INFERENCE,
        last_mentioned=NOW - timedelta(days=4),
        id=pid,
        updated_at=NOW - timedelta(days=1),
    )
    store = AsyncMock()
    store.get = AsyncMock(return_value=person)
    ref = ScreenRef(kind="contact", id=str(pid), label="Ana (confirmed)")
    [line] = await ContactScreenResolver(store).resolve([ref], ResolveContext(now=NOW))
    assert line.label == "Ana Costa"
    assert (
        line.summary
        == "professional, client, last mentioned 4 d ago, not yet confirmed by you"
    )
    assert (line.posture.kind, line.posture.confidence) == (ClaimKind.INFERENCE, 0.6)
    store.get = AsyncMock(return_value=None)
    [gone] = await ContactScreenResolver(store).resolve([ref], ResolveContext(now=NOW))
    assert gone.status is ScreenStatus.MISSING
