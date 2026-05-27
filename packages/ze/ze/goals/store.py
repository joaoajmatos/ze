"""Re-export ze-core Postgres goal store (Phase 5 migration)."""

from ze_core.goals.postgres import PostgresGoalStore as GoalStore
from ze_core.goals.postgres import _gate_from_row, _goal_from_row, _milestone_from_row

__all__ = ["GoalStore", "_goal_from_row", "_milestone_from_row", "_gate_from_row"]
