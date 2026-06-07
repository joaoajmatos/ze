---
name: project-phase24-goal-collaboration
description: Phase 24 done — goal-aware routing, conversational steering, post-goal retrospective, weekly GoalNarrativeJob
metadata:
  type: project
---

Phase 24 adds the collaboration layer on top of Phase 23 ([[project-phase23-goal-engine-v2]]):

**1. Goal-aware routing** (`ze_core/orchestration/graph.py`, `state.py`, `plugin.py`, `ze_personal/graph/routing_context.py`)
- `routing_hints: str | None` added to `AgentState` and `make_graph_input`
- `ZePlugin.pre_route_node()` hook: returns a node inserted between `preprocess` and `embed_route`
- `PersonalPlugin.pre_route_node()` returns `inject_goal_routing_context`
- `inject_goal_routing_context` reads `goal_store` from configurable, builds a ≤300-char hint string listing active goals + current milestone (or pending gate), stores in `state["routing_hints"]`
- `embed_route` appends hints AFTER the message text (not prepended — avoids misdirection for non-goal messages)
- `goal_store` added to `ZeContainer._build_config()` so the node can access it at runtime

**2. Conversational steering** (`executor.py`, `tools.py`, `agent.py`)
- `GoalExecutor._steer_queues`: in-memory `asyncio.Queue` per goal (not persisted — known limitation)
- `GoalExecutor.steer(goal_id, instruction) -> bool`: only works for `ACTIVE` goals; returns `False` for `AWAITING_GATE`
- `_advance_unlocked` drains one steer per cycle before picking the next milestone
- `_apply_steer`: notifies user, replans, replaces pending milestones/gates, resets `consecutive_failures`, resumes
- `steer_goal` tool added to `GoalAgent`; agent instructions updated to explain gate-first requirement

**3. Post-goal retrospective** (`planner.py`, `executor.py`)
- `GoalPlanner.synthesize_retrospective(goal, milestones, learnings)` — LLM, 3-5 paragraphs
- `GoalPlanner.synthesize_weekly_narrative(goal, completed_this_week, pending_gate, next_milestones)` — 1 paragraph
- Completion push replaced with `_push_retrospective()` — falls back to `goal.success_condition` on exception

**4. Weekly GoalNarrativeJob** (`ze/jobs/goal_narrative.py`, `ze/container.py`, `config.yaml`)
- Runs Sunday 18:00 (`0 18 * * 0`); dedup: skips if sent within 144h (6 days)
- Per-goal paragraphs assembled; skips goals with no progress this week AND no pending gate
- Resilient per-goal: one goal's LLM failure doesn't block others
- Wired in `build_container`; stored as `ZeContainer.goal_narrative`

**Key invariants:**
- Steer queue is in-memory only — lost on restart. User must re-send after restart.
- `steer()` rejects `AWAITING_GATE` — gate must be resolved first
- `pre_route_node()` DB read failure returns `routing_hints: None` — routing unaffected

**Why:** Goals were invisible at routing time; users had no natural way to redirect mid-execution; completions were terse; progress was silent between gates. Phase 24 makes goal collaboration feel continuous and natural.
