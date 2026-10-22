import pytest

from ze_automation.goals import lifecycle
from ze_automation.goals.types import GoalStatus

PAUSABLE = {GoalStatus.ACTIVE, GoalStatus.AWAITING_GATE}
ABANDONABLE = {
    GoalStatus.PLANNING,
    GoalStatus.ACTIVE,
    GoalStatus.AWAITING_GATE,
    GoalStatus.PAUSED,
}
RESUMABLE = {GoalStatus.PAUSED}


@pytest.mark.parametrize("status", list(GoalStatus))
def test_can_pause(status):
    assert lifecycle.can_pause(status) is (status in PAUSABLE)


@pytest.mark.parametrize("status", list(GoalStatus))
def test_can_abandon(status):
    assert lifecycle.can_abandon(status) is (status in ABANDONABLE)


@pytest.mark.parametrize("status", list(GoalStatus))
def test_can_resume(status):
    assert lifecycle.can_resume(status) is (status in RESUMABLE)
