# Implementation Plan: Session Context Continuity

**Branch**: `112-session-context-continuity` | **Date**: 2026-08-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/112-session-context-continuity/spec.md`

## Summary

**Correction found during planning (confirmed with the user before proceeding)**: the
spec's premise — "currently unbounded `AgentState.messages` growth" — does not match
the code. `write_memory` (`core/ze-core/ze_core/orchestration/nodes/memory.py:111-116`)
already hard-caps checkpointed `state["messages"]` at the last `SESSION_HISTORY_LIMIT`
(10) entries every turn; the real failure mode is a silent 5-turn memory cliff (blind
trim, no summary), not a hard context-capacity error. `fetch_context`
(`nodes/context.py:62-68`) also already runs the exact gap check FR-006/FR-009 need,
against the same `session_inactivity_minutes` config key `SessionSummariser` uses — but
today it just blanks history to `[]` on a long gap, the literal "blank slate" US2
complains about. This plan targets those two existing mechanisms rather than adding
parallel new ones. See research.md R1 for the full finding.

Two additions, both engine-level (`ze-core`) since they apply uniformly across every
plugin/agent, with no new database tables and no new graph nodes:

1. **Mid-session compaction** — inside `write_memory`, before the existing
   `updated[-SESSION_HISTORY_LIMIT:]` trim, check the pre-slice message list's estimated
   token count against 70% of the routed model's context window (a new static per-model
   table with a conservative fallback). Only when exceeded does the trim change: the
   verbatim tail stays the same size, but everything before it is folded into one
   LLM-produced rolling summary message instead of being dropped. This is an in-place
   `update_state` on the existing thread lineage (no checkpoint branching, using the
   exact mechanism `write_memory` already uses for its `[-10:]` trim), and never
   touches the durable `messages` table record — only the graph-state copy sent to the
   model.
2. **Resume recap** — inside `fetch_context`'s existing gap-check branch, when the gap
   since `last_active_at` exceeds the shared inactivity threshold, assemble a recap from
   existing tracked state (latest session narrative, `LoopSurfacer` open-loop
   candidates, in-flight goals/workflows) into `AgentContext.resume_recap` — set on the
   same `agent_context` object this node already constructs — rendered into the system
   prompt the same way `screen_context_note` already is. It is never appended to
   `state["messages"]`, so it cannot surface as a visible chat message.

Both are recorded per-turn on the existing `MessageTrace`/`trace` JSONB column (Phase
89), extended with two new optional fields, for User Story 3's transparency
requirement.

## Technical Context

**Language/Version**: Python 3.11 (existing `ze-core` toolchain)

**Primary Dependencies**: LangGraph (graph nodes, `AsyncPostgresSaver` checkpointing —
already in place), the injected `LLMClient`/`OpenRouterClient` (existing, no new
provider SDK — Constitution VII), no new third-party tokenizer dependency
(research.md R4)

**Storage**: PostgreSQL — no new tables/migrations. Reuses `sessions.last_active_at`,
`messages.trace` (JSONB, existing column from `zc020_message_trace.py`), `ze-memory`'s
session-summary store, `ze-worldstate`'s `open_loops`, `ze-automation`'s
goals/workflows tables — all read-only from this feature's perspective.

**Testing**: pytest (`make test-core`), mirroring `core/ze-core/tests/orchestration/
nodes/` conventions (dataclass fakes/`AsyncMock` for `config["configurable"]`, minimal
hand-built `AgentState`, no full graph run). SC-002 (recall accuracy) validated through
`eval/run.py` against scripted scenarios in `eval/scenarios/`, not pytest.

**Target Platform**: Existing `ze-api` backend service (Linux/Docker, per current
deployment) — no new deployment surface.

**Project Type**: Backend-only addition to an existing monorepo package
(`core/ze-core`); no new package, no frontend change required to satisfy the spec's
functional requirements (the trace panel *rendering* the new fields is a natural
follow-up but not a blocking requirement — FR-011 only requires inspectability via the
existing trace surface, which the REST payload already provides).

**Performance Goals**: SC-004 — compaction must add no perceptible delay beyond the
normal cost of one extra LLM call on the turn that triggers it (i.e., no synchronous
work beyond that one summarization call; no live network calls to resolve context
window size — research.md R3).

**Constraints**: 70% trigger threshold is fixed by the spec (FR-001), not configurable
per-model; the resume-recap inactivity threshold MUST remain identical to
`SessionSummariser`'s existing `session_inactivity_minutes` (FR-006) — no second config
knob.

**Scale/Scope**: Single-user system (Constitution II) — one thread's compaction/recap
state never interacts with another user's; SC-001 targets 500+ turns per thread.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Spec-First Development | Spec exists at `specs/phases/112-session-context-continuity/spec.md`, status will move to Implemented in the same commit as the code (per prior phases' pattern, e.g. Phase 111) | PASS |
| II. Single-User Model | No `user_id`/tenancy introduced; goal/workflow "relevance" resolved as global-because-single-user (research.md R5), not a new per-thread scoping column | PASS |
| III. Layered Package Architecture | New nodes and the context-window table live in `core/ze-core` (engine, no domain knowledge — reads generic message/session/loop/goal/workflow shapes, not plugin-specific data). Resume-recap assembly reads `ze-memory`, `ze-worldstate`, `ze-automation` — all already core-layer, already engine-accessible per the existing dependency graph (`ze-core → ze-agents, ze-communication, ze-plugin`; goal/workflow/loop/memory stores are wired into `config["configurable"]` by the container, the existing seam `surface_loops` already uses). No plugin-domain vocabulary is hardcoded into a core enum — the recap only names generic entity kinds (loop/goal/workflow), not plugin identities. | PASS |
| IV. Typed, Explicit Python | `RollingSummary`, `ResumeRecap`, `CompactionTrace` are dataclasses in `types.py`-style modules, not Pydantic (Pydantic stays confined to `ze_api/api/schemas.py`, which is untouched — the trace REST route's `response_model` already exists and just gains fields on its existing dataclass). Failure fallback (R7) raises no bare exceptions — it catches and degrades gracefully as FR-010 requires. | PASS |
| V. Test Discipline | New pytest coverage for both nodes + the context-window table, no real DB/LLM (mocked `config["configurable"]` deps, mocked `client.complete`), mirrors existing `nodes/test_loop_surfacing.py` pattern | PASS |
| VI. Explicit Persistence | No new tables — explicitly verified against alternatives in research.md R2/R6; the one existing column touched (`trace` JSONB) already exists from `zc020_message_trace.py`, no migration needed | PASS |
| VII. One LLM Gateway, Local Embeddings | Compaction's summarization call goes through the existing injected `LLMClient`/`OpenRouterClient`, no direct provider SDK, no new API key | PASS |

No violations — Complexity Tracking section is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/phases/112-session-context-continuity/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── graph-nodes.md    # write_memory / fetch_context node-edit contracts
│   └── trace-schema.md   # MessageTrace JSON shape extension
└── tasks.md              # Phase 2 output (/speckit-tasks — not created by this command)
```

### Source Code (repository root)

This is an addition to the existing `core/ze-core` package inside Ze's established
monorepo layout (see root `CLAUDE.md` — not a new project type; no Option 1/2/3
scaffolding applies). Concrete paths touched:

```text
core/ze-core/
├── ze_core/
│   ├── openrouter/
│   │   └── context_windows.py       # NEW — MODEL_CONTEXT_WINDOWS, get_context_window()
│   ├── orchestration/
│   │   ├── state.py                 # EDIT — AgentState: compaction_span,
│   │   │                            #   resume_recap_applied
│   │   └── nodes/
│   │       ├── memory.py            # EDIT — write_memory: token-budget check +
│   │       │                        #   LLM-summarization branch before the
│   │       │                        #   existing [-SESSION_HISTORY_LIMIT:] trim
│   │       ├── context.py           # EDIT — fetch_context: resume-recap assembly
│   │       │                        #   inside the existing gap-check branch
│   │       └── trace.py             # EDIT — record_trace reads the two new
│   │                                #   AgentState fields
│   └── conversation/messages/
│       └── types.py                 # EDIT — MessageTrace: compaction, resume_recap_applied
└── tests/orchestration/nodes/
    ├── test_context_windows.py      # NEW (module lives under ze_core/openrouter/, test
    │                                #   mirrors it under tests/orchestration/ for
    │                                #   proximity to the node tests that consume it)
    ├── test_memory.py               # EDIT — add compaction branch cases
    └── test_context.py              # NEW — fetch_context has no test file today;
                                      #   covers both the pre-existing gap-check and
                                      #   the new resume-recap branch

core/ze-agents/ze_agents/
├── types.py                         # EDIT — AgentContext.resume_recap: str | None
└── base_agent.py                    # EDIT — _build_system_prompt renders resume_recap

eval/scenarios/                      # NEW scenario file(s) for SC-002 recall validation
```

**Structure Decision**: Everything lives inside the existing `core/ze-core` and
`core/ze-agents` packages — no new package, no new graph nodes (this replaces logic
inside two existing nodes, `write_memory` and `fetch_context`, rather than adding new
ones — research.md R1). The one cross-package touch (`AgentContext` in `ze-agents`) is
the existing, established seam for injecting runtime prompt context — no violation of
the dependency graph.

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*
