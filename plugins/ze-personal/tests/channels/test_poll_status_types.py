from ze_personal.channels.types import ChannelPollStatus, PollOutcome


def test_poll_outcome_values():
    assert [o.value for o in PollOutcome] == ["ok", "auth_failed", "failed"]


def test_status_defaults_are_explicit():
    status = ChannelPollStatus(watermark=None, last_outcome=None, last_outcome_at=None)
    assert status.last_outcome is None
