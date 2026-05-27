"""Re-export ze-core goal types (Phase 5 migration)."""

from ze_core.goals.types import (
    GateStatus,
    Goal,
    GoalLearning,
    GoalStatus,
    Milestone,
    MilestoneStatus,
    VerificationGate,
)

__all__ = [
    "Goal",
    "GoalLearning",
    "GoalStatus",
    "GateStatus",
    "Milestone",
    "MilestoneStatus",
    "VerificationGate",
]
