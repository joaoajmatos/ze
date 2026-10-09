# Research: Response Feedback and Retry

## R1. How retry rewinds a turn
Context: `write_memory` appends the exchange to checkpointed `messages`; `make_graph_input` deliberately omits `messages` so history survives. A regenerate must start from the state before the original user message.
Decision: fork from the checkpoint taken before the original turn (LangGraph checkpoint history, `graph.aget_state_history`), keyed by recording `checkpoint_id` at turn start in the user message row is NOT required; select the newest checkpoint whose `messages` length equals the length before the user message. Fallback if forking is unreliable with `AsyncPostgresSaver`: `aupdate_state` that removes the last user/assistant pair from `messages`. Spike first (task T014); the spike decides and the result is written back here.
Rejected: re-running with history passed in the prompt (diverges from the graph's real context); mutating the stored thread outside the graph (checkpoint and `messages` table disagree).

## R2. Target face
`TargetFace.WORLD` (as ActionRecord): the evidence is about Ze's output in the world, not a claim about the user. Using `USER` would invite user-profile consumers.

## R3. Nested tool calls
Phase 151 nests specialist `tool_calls` under `delegate_to_agent`. `_iter_tool_calls` reads `agent_result.tool_calls`; verify nested calls are flattened (`ze_agents/nested_tools.py`). If not, flatten in `record_trace`. Test: a companion turn whose delegate sends mail is `has_irreversible_action`.

## R4. Superseded messages in later context
Superseded messages stay in the `messages` table but the checkpointed `messages` channel only holds the replacement (R1). Session history UI and `list_by_thread` default exclude superseded rows. Resume recap (112) reads the checkpoint, so it never sees them.

## R5. WRITE tool inventory
About 50 `@tool(access=WRITE)` declarations across ze-priority, ze-automation (goals, workflow), ze-workspace, ze-calendar, ze-messenger, ze-ingestion, ze-finance, ze-personal (companion, contacts, social, others), ze-prospecting. Each package's task lists its tools; classification follows spec "Deferred" inventory; borderline tools default to `IRREVERSIBLE`. A test asserts every registered WRITE tool declares reversibility and every `undo_tool` resolves.

## R6. Trace retention
No trace pruning job exists today (grep `trace` in jobs: none). FR-009 is satisfied by documenting that traces must not be pruned while feedback exists; add a guard in the message store's trace-clearing paths if any appear (verify during implementation).

## R7. Phrase text for reasons
Reason text names actions in plain words. Each WRITE tool declares `effect_phrase` (e.g. "set a reminder"). Fallback is the tool name humanized (`shared/lib/humanize.ts` style on the backend), so a missing phrase never hides an action.
