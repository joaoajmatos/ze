from __future__ import annotations

from ze_proactive.types import PushKind

WORKFLOW_FAILURE = PushKind("workflow_failure", "accountability", "high", "workflows")
GOAL_PLAN_PROPOSED = PushKind("goal_plan_proposed", "accountability", "high", "goals")
GOAL_ATTENTION_NEEDED = PushKind(
    "goal_attention_needed", "accountability", "high", "goals"
)
GOAL_PLAN_ADAPTED = PushKind("goal_plan_adapted", "accountability", "normal", "goals")
GOAL_MILESTONE_DONE = PushKind(
    "goal_milestone_done", "accountability", "normal", "goals"
)
GOAL_COMPLETED = PushKind("goal_completed", "accountability", "normal", "goals")
GOAL_GATE = PushKind("goal_gate", "accountability", "high", "goals")
COST_ANOMALY = PushKind("cost_anomaly", "accountability", "high", "accountability")
ACCOUNTABILITY_NARRATIVE = PushKind(
    "accountability_narrative", "accountability", "normal", "accountability"
)
GOAL_NARRATIVE = PushKind("goal_narrative", "accountability", "normal", "goals")
STUCK_GOAL = PushKind("stuck_goal", "discretionary", "normal", "goals")
GOAL_SUGGESTION = PushKind("goal_suggestion", "discretionary", "normal", "goals")
GOAL_OVERLAP = PushKind("goal_overlap", "discretionary", "normal", "goals")
GOAL_REUSE = PushKind("goal_reuse", "discretionary", "low", "goals")
WRITE_APPROVAL_HELD = PushKind(
    "write_approval_held", "requested", "normal", "automation", in_chat=False
)
