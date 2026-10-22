from ze_automation.goals.types import GoalStatus

_PAUSABLE = frozenset({GoalStatus.ACTIVE, GoalStatus.AWAITING_GATE})
_ABANDONABLE = frozenset(
    {
        GoalStatus.PLANNING,
        GoalStatus.ACTIVE,
        GoalStatus.AWAITING_GATE,
        GoalStatus.PAUSED,
    }
)
_RESUMABLE = frozenset({GoalStatus.PAUSED})


def can_pause(status: GoalStatus) -> bool:
    return status in _PAUSABLE


def can_abandon(status: GoalStatus) -> bool:
    return status in _ABANDONABLE


def can_resume(status: GoalStatus) -> bool:
    return status in _RESUMABLE
