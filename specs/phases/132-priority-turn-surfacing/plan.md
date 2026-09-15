# Implementation Plan: Priority Turn Surfacing

**Branch**: `132-priority-turn-surfacing` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/phases/132-priority-turn-surfacing/spec.md`

## Summary

Conversation turns and session-resume recap stop mentioning open loops through
their own path. A new `TurnSurfacing` service in `ze-priority` reads the merged
`PriorityView` snapshot (rank plus Phase 127 pins), filters unsolicited mentions
by topical relevance, and returns a short ranked list. The existing
`surface_loops` graph node keeps its name and stays in `ze-core`; it is injected
with `turn_surfacer` the same way it is injected with `loop_surfacer` today, so
the engine never imports `ze-priority`. Explicit "what's open" questions inject
the same ranking into the system prompt. Push budget and store layout do not
change.

## Technical Context

**Language/Version**: Python 3.11 (repo-wide pin)

**Primary Dependencies**: No new third-party packages. Uses existing
`PriorityView`, `merge()`, `LoopStore` graph overlap, and LangGraph
`config["configurable"]` injection.

**Storage**: None. No migration.

**Testing**: pytest, `asyncio_mode = "auto"`; mock stores / `PriorityView` /
`turn_surfacer` with `AsyncMock`. No real DB, no real LLM.

**Target Platform**: Existing backend (`ze-api` composition root). No new
frontend surface (`ze-web` does not render today's `drifting_loops` component).

**Project Type**: In-tree core package change (`ze-priority` + `ze-core` graph
node + `ze-agents` context field).

**Performance Goals**: One extra `rank()` + in-memory merge + one graph
relationship read per turn that has resolved entities. Same working-set scale
as Phase 123 (<500ms for tens of items).

**Constraints**: `ze-core` must not import `ze-priority` or `ze-worldstate`.
No loop-only fallback. No push-budget change. No store merge.

**Scale/Scope**: Single user; mention list capped at 3 unsolicited items.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Spec-First Development | Spec at `specs/phases/132-priority-turn-surfacing/spec.md`; status Draft → Planned in the plan commit, Done with implementation. | PASS |
| II. Single-User Model | No `user_id`; ranking and mentions are process-global. | PASS |
| III. Layered Package Architecture | `TurnSurfacing` lives in `ze-priority` (core, already the `PriorityView` owner). `ze-core` consumes it only via `config["configurable"]["turn_surfacer"]` — no new engine import, matching Phase 110's `loop_surfacer`. No plugin-domain vocabulary added to a core enum; `source_kind` stays the existing string literal. Companion stays a plugin; it sees the ranked list through `AgentContext.open_priorities_note`, not a `ze_core` import. | PASS |
| IV. Typed, Explicit Python | `OpenItemMention` dataclass in `types.py`; `TurnSurfacing` constructor-injected; errors already `ZePriorityError`; async I/O; `get_logger(__name__)`. | PASS |
| V. Test Discipline | Unit tests in `ze-priority/tests/test_turn.py`, `ze-core/tests/orchestration/nodes/test_loop_surfacing.py`, `test_context.py`. Mocks only. | PASS |
| VI. Explicit Persistence | No schema change. | PASS |
| VII. One LLM Gateway, Local Embeddings | No new LLM or embedding call site (R3). | PASS |
| VIII. Pre-v1 Hard Cuts | Component type `drifting_loops` → `open_items`; recap fields `open_loop_lines`/`in_flight_goal_lines` → `open_item_lines`. No shim, dual-write, or loop-only fallback. | PASS |

No violations. Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/phases/132-priority-turn-surfacing/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── turn_surfacing.md
└── tasks.md              # /speckit-tasks — not created here
```

### Source Code (repository root)

```text
core/arbitration/ze-priority/ze_priority/
├── turn.py                 # NEW: TurnSurfacing
├── types.py                # OpenItemMention; PriorityItem additive fields
├── scoring.py              # fill linked_entity_ids / match_text / hedge
├── view.py                 # unchanged rank()/rank_subset()
└── tests/test_turn.py      # NEW

core/engine/ze-core/ze_core/orchestration/nodes/
├── loop_surfacing.py       # surface_loops reads turn_surfacer
└── context.py              # resume recap + open_priorities_note

core/contracts/ze-agents/ze_agents/
├── types.py                # AgentContext.open_priorities_note
└── base_agent.py           # prepend open_priorities_note in system prompt

apps/ze-api/ze_api/
└── container.py            # build TurnSurfacing, put on configurable

specs/arch/attention-arbitration.md   # close "Surfacing consumer" question
```

**Structure Decision**: Keep ranking in `ze-priority`; keep the graph node name
`surface_loops` in `ze-core`; wire at the `ze-api` composition root. Do not add
a `ze-core → ze-priority` package edge.
