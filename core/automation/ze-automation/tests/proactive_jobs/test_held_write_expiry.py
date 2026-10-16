from datetime import datetime, timezone
from unittest.mock import AsyncMock

from ze_automation.holds.resumer import HeldWriteNotOpenError
from ze_automation.holds.types import HeldWrite
from ze_automation.jobs.held_write_expiry import HeldWriteExpiryJob

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def _hold(request_id: str) -> HeldWrite:
    return HeldWrite(request_id=request_id, source="workflow", owner_ref="e1")


async def test_expired_holds_resume_as_a_timeout() -> None:
    store = AsyncMock()
    store.list_expired = AsyncMock(return_value=[_hold("a"), _hold("b")])
    resumer = AsyncMock()
    resumer.decide = AsyncMock(side_effect=lambda rid, choice: _hold(rid))
    job = HeldWriteExpiryJob(store, resumer, clock=lambda: NOW)

    await job.run()

    store.list_expired.assert_awaited_once_with(NOW)
    assert [c.args for c in resumer.decide.await_args_list] == [
        ("a", "timeout"),
        ("b", "timeout"),
    ]
    assert resumer.run.await_count == 2


async def test_a_hold_answered_meanwhile_is_skipped() -> None:
    store = AsyncMock()
    store.list_expired = AsyncMock(return_value=[_hold("a")])
    resumer = AsyncMock()
    resumer.decide = AsyncMock(side_effect=HeldWriteNotOpenError("a"))

    await HeldWriteExpiryJob(store, resumer, clock=lambda: NOW).run()

    resumer.run.assert_not_awaited()
