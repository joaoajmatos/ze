# Phase 1 Data Model: Session Context Continuity

No new database tables. This feature only adds in-process/state types and extends one
existing JSONB payload shape (`messages.trace`). See research.md R2/R6 for why no new
migration is needed.

## `ContextBudget` (new, `core/ze-core/ze_core/openrouter/context_windows.py`)

Static lookup, not a persisted entity.

| Field | Type | Notes |
|---|---|---|
| `MODEL_CONTEXT_WINDOWS` | `dict[str, int]` | model slug → context length in tokens |
| `DEFAULT_CONTEXT_WINDOW_TOKENS` | `int` | conservative fallback (FR-005) |

Accessor: `get_context_window(model: str) -> int`.

## `RollingSummary` (new, transient — lives only inside a turn's `AgentState`)

| Field | Type | Notes |
|---|---|---|
| `text` | `str` | condensed content (FR-003): decisions, constraints, outstanding tasks, outcomes |
| `covers_through_index` | `int` | index into the pre-compaction `messages` list; last message folded into the summary |
| `produced_at` | `datetime` | for trace/debugging |

Not stored on its own — it is written into `state["messages"]` as a single synthetic
`{"role": "system", "content": text, "compaction_summary": true}` dict entry (the
`compaction_summary` marker key lets `record_trace` and any future consumer detect it
without a separate field), and it becomes part of the checkpointed lineage per R2.

## `ResumeRecap` (new, transient — lives only inside a turn's `AgentContext`)

| Field | Type | Notes |
|---|---|---|
| `session_narrative` | `str \| None` | from `get_session_summary(session_id)`, may be absent |
| `open_loop_lines` | `list[str]` | formatted from `LoopSurfacer` entity-overlap candidates |
| `in_flight_goal_lines` | `list[str]` | from `GoalStore` active-goal listing |
| `in_flight_workflow_lines` | `list[str]` | from `WorkflowStore` active-execution listing |
| `gap_minutes` | `float` | for trace/debugging, not shown to user |

Empty when nothing outstanding (FR-008) — in that case `_assemble_resume_recap` (the
helper `fetch_context` calls, research.md R5) sets `AgentContext.resume_recap = None`
rather than an empty-but-present string, so `_build_system_prompt` renders nothing
extra.

Rendering: `ResumeRecap.render() -> str` produces the block injected into
`AgentContext.resume_recap`, consumed by `BaseAgent._build_system_prompt` exactly like
`screen_context_note` (never appended to `state["messages"]` — FR-007a).

## `AgentState` extensions (`core/ze-core/ze_core/orchestration/state.py`)

| Field | Type | Notes |
|---|---|---|
| `compaction_span` | `tuple[int, int] \| None` | `(0, covers_through_index)` set by `write_memory`'s compaction branch when it ran this turn, else `None`; read by `record_trace` |
| `resume_recap_applied` | `bool` | set by `fetch_context`'s resume-recap branch, read by `record_trace` |

`messages` (existing field) is mutated in place by `write_memory`'s existing
return-and-replace mechanism (research.md R2) — no new field needed to hold the
compacted form, and no new graph node (research.md R1).

## `MessageTrace` extension (`core/ze-core/ze_core/conversation/messages/types.py`)

Existing dataclass fields: `agent, routing_method, confidence, score_gap, is_compound,
subtasks, memory_chunks, tool_calls, total_duration_ms`.

New fields:

| Field | Type | Notes |
|---|---|---|
| `compaction` | `CompactionTrace \| None` | `None` when compaction did not run this turn |
| `resume_recap_applied` | `bool` | default `False` |

New nested type `CompactionTrace`:

| Field | Type | Notes |
|---|---|---|
| `span_start` | `int` | always `0` today (compaction always folds from the beginning) |
| `span_end` | `int` | index of the last message folded into the summary |

Both are optional/defaulted so existing serialized traces (pre-Phase-112 messages)
deserialize unchanged — no backfill migration required.

## State transitions

None — this feature adds no entity with a lifecycle. `Conversation Thread` (spec's Key
Entity) already exists as `sessions`/`thread_id`; `Rolling Summary` and `Resume Recap`
are per-turn derived artifacts, not persisted entities with their own state machine.
