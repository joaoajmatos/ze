# Feature Specification: Typed Turn Services

**Feature Branch**: `201-typed-turn-services`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 200

**Input**: Architecture review 2026-10-22, candidate C2. A typed `TurnServices` and a `TurnRequest` replace the string keys in `config["configurable"]`. The container folds contributions from each core package's `*Stack`. Plugins provide services by type. Delete the core `Container.invoke`/`resume`/`from_config` and the duplicate `_build_config`.

## Context

This is a deepening refactor. Its users are the maintainers who add a service to Ze, and the plugin authors whose graph code reads services. The guarantee it protects is one the user sees: every part of a turn that should run does run, and a missing service is an error at startup, not a silent no-op.

Every graph node and several plugins reach their dependencies through `config["configurable"]`, an untyped dictionary keyed by strings. Facts checked on 2026-10-22:

- **Two builders that disagree.** The core `Container._build_config` (`core/engine/ze-core/ze_core/container.py:51-69`) and `ZeContainer._build_config` (`apps/ze-api/ze_api/wiring/container.py:314-360`) build the dictionary separately, and the ze-api one does not call the core one. The core builder sets `turn_extractor`; the ze-api builder does not. In production, `write_memory`'s turn extractor (`ze_core/orchestration/nodes/memory.py:225`) therefore never runs, so no events or entity proposals come from conversation turns (bug B2; phase 198 patches it).
- **A key nobody sets.** The workflow graph reads `workflow_scheduler` to stop a cancelled run between steps (`plugins/ze-personal/ze_personal/graph/workflow.py:62`, `:459`). No builder sets that key, so the check is always skipped. This needs confirming in planning: cancellation may be handled elsewhere.
- **About 45 distinct keys.** They are read from files in ze-core (13 files), ze-api (4), ze-automation (3), ze-personal (2), ze-plugin, ze-worldstate, ze-memory and ze-skills (1 each). Plugins read keys that ze-api sets: `memory_hooks.py:38-42` reads `person_store`, `contact_channel_store`, `collision_store`, `nli_client` and `memory_store`; `graph/workflow.py` reads `workflow_store`, `openrouter_client`, `settings`, `workflow_planner` and `procedure_admission`. These reads get around the plugin boundary test (`packages/ze-sdk/tests/test_plugin_boundaries.py`), which checks imports, not string keys.
- **One key, two shapes.** `settings` is sometimes a dictionary and sometimes an object. Each reader handles both (`nodes/memory.py:312,327,353`, `nodes/context.py:255,335`, `nodes/preprocessing.py:27`, `nodes/correlation.py:98,107`, `conversation/turn.py:161`).
- **Magic merges.** Plugin services are merged with `dict.update` in both builders (`ze_core/container.py:55`, `wiring/container.py:317`). `memory_hooks` and `identity_builder` are reserved keys inside that flat dictionary (`ze_personal/plugin.py:258-268`). A second plugin returning `memory_hooks` silently replaces the first.
- **Private calls from outside.** `_build_config` is private, but `api/eval/router.py:106` and `api/ws/confirmation.py:130` call it.
- **Per-turn values mixed with services.** `retry_mode`, `screen_context`, `screen_context_invalid`, `forced_agent`, `user_message_id`, `tool_sink`, `abort_token` and `purge` arrive as extra keys in the same dictionary as long-lived services (`eval/router.py:59-64`, `ws/turns.py:556`, `ws/confirmation.py:386`, `conversation/turn.py:256,476`).
- **No locality for a new service.** A new core service is registered by hand in up to six places: a `ZeContainer` field (65 fields today), the constructor call (`wiring/container.py:646-724`), a `_build_config` key, a getter in `api/deps.py` (30 `get_*` functions), an entry in `build_dep_map` (`wiring/agents.py:63-110`), and the job, data-domain, screen or migration lists. `container.py` is the most-changed file in the repo; phases 184, 185, 192, 194, 195 and 197 each edited it.
- **Dead entry points.** Core `Container.invoke` (`ze_core/container.py:71`), `resume` (`:167`) and `from_config` (`:218`) are used only by core tests (`core/engine/ze-core/tests/test_container_invoke.py`). Production runs turns through `ZeContainer.invoke_raw_turn`/`resume_turn`, which override `from_config`. `invoke` contains a fourth, unused confirmation style.
- **Stacks already exist.** Seven core packages already return a `*Stack` from their `bootstrap.py`: `EngineStack`, `WorldstateStack`, `CorrelationStack`, `WorkspaceStack`, `IngestionStack`, `SkillsStack`, `AutomationStack`. They have no common contribution shape.

**Blast radius** (graphify, 2026-10-22):
- `_build_config`: 7 source and 6 test references, all in ze-api.
- `ZeContainer`: 6 source and 10 test references in ze-api.
- Every orchestration node in ze-core reads `config["configurable"]`, and so do the plugin and core readers listed above.
- `make_graph_input` callers: see phase 200.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A turn's services are typed and complete (Priority: P1)

A maintainer writes or changes a graph node. It reads its dependencies as typed attributes of one turn-services value. A service that a deployment may leave out is an explicit optional field. A required service that is missing stops startup with an error naming it.

**Why this priority**: The missing `turn_extractor` (B2) and the never-set `workflow_scheduler` show that today's dictionary fails silently. A maintainer cannot see what a turn can reach without reading two builders and every plugin.

**Independent Test**: Build the production container with one required service missing: startup fails and names it. Build it complete: a contract test lists every service a node reads, and asserts that each is a field of the turn services and is non-null where it is required.

**Acceptance Scenarios**:

1. **Given** the production container, **When** a conversation turn runs, **Then** the turn extractor runs (B2 cannot recur).
2. **Given** a workflow run is cancelled, **When** the next step loads, **Then** the cancellation check sees the scheduler. Or the check is deleted if planning shows cancellation is enforced elsewhere.
3. **Given** a node test, **When** it is written, **Then** it passes a typed fake turn-services value rather than a hand-built dictionary.
4. **Given** `settings`, **When** any node reads it, **Then** it gets one type; no reader branches on a dictionary or an object.

---

### User Story 2 - Per-turn values are a separate request (Priority: P1)

A caller that starts or resumes a turn (WebSocket message, Retry, confirmation resume, eval, workspace follow-up) passes one typed turn-request value: retry mode, screen context, forced agent, user message id, and the sinks and abort token for this turn. It never edits the services dictionary.

**Why this priority**: Callers today reach into a private builder (`eval/router.py:106`, `ws/confirmation.py:130`) to add string keys, and the eval path sets keys the product path does not.

**Independent Test**: Every turn entry point builds a turn request. A grep finds no `_build_config` call outside the container, and no string-keyed per-turn value.

**Acceptance Scenarios**:

1. **Given** a Retry, **When** the turn starts, **Then** `retry_mode` arrives through the turn request and every write gate sees it.
2. **Given** an eval turn with a forced agent and a screen context, **When** it runs, **Then** both arrive through the same turn request the WebSocket path uses.

---

### User Story 3 - Adding a core service touches one package (Priority: P2)

A maintainer adds a service to a core package. They declare it in that package's stack contributions: turn services, agent dependencies, REST access, proactive jobs, data domains, screen resolvers, migrations path. The container folds the contributions of every core stack, then every plugin, and builds the turn services, the agent dependency map and the app's typed attributes from that fold.

**Why this priority**: `container.py` churn and the six hand lists come from this missing seam. It is also what lets phases 207, 210 and 211 move code without editing the container each time.

**Independent Test**: Add a fake service to one stack in a test: it appears in the turn services, the agent dependency map and the REST attributes with no edit to the container.

**Acceptance Scenarios**:

1. **Given** a new service declared in the worldstate stack, **When** the app starts, **Then** nodes, agents and routers can reach it, and `wiring/container.py` was not edited.
2. **Given** two plugins both contribute the same service type, **When** the app starts, **Then** startup fails and names both plugins.
3. **Given** a plugin contributes turn hooks (today's `memory_hooks`) or an identity builder, **When** the turn runs, **Then** they come from typed contribution lists, and all plugins' hooks run.

---

### User Story 4 - One turn entry point (Priority: P3)

The core container's unused `invoke`, `resume` and `from_config`, and its duplicate `_build_config`, are deleted. Their tests move to the entry point production uses, or are deleted.

**Why this priority**: The dead path holds a second config builder and a fourth confirmation style that readers mistake for the real one.

**Independent Test**: The core container has no turn entry point. The ze-core suite passes through `invoke_raw_turn`/`resume_turn` with a test container.

**Acceptance Scenarios**:

1. **Given** the engine package, **When** a maintainer looks for how a turn starts, **Then** there is one function to read.

---

### Edge Cases

- **Workflow graph.** The workflow graph runs with its own state extension. Its nodes read the same services, and `workflow_scheduler` becomes a typed field.
- **Optional deployments.** With no workspace sidecar, no System One client or no commitment intake, the field is `None`, and the reader handles `None` explicitly, as it does today. The difference is that `None` is declared, not accidental.
- **LangGraph checkpoints.** Services are invocation-time values (`langgraph-orchestration.md`) and must never be checkpointed. The turn services value lives in `config`, not in graph state.
- **Plugin ordering.** Services contributed by a plugin that another plugin needs at construction stay in the existing topological plugin order. Late binding through `startup()` is phase 210's concern, not this phase's.
- **Tests that build configs by hand.** Dozens of tests write `{"configurable": {...}}`. They move to a test helper that builds a typed fake.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Graph nodes, the workflow graph and plugin graph code MUST read services from one typed turn-services value. Reading a service by string key from `config["configurable"]` MUST NOT remain anywhere in source code.
- **FR-002**: Each service MUST be a declared field: required (non-null at startup) or optional (explicitly `None` when absent). Startup MUST fail with the service name when a required service is missing.
- **FR-003**: Per-turn values MUST travel in a separate typed turn request, built by every turn entry point: WebSocket message, Retry, confirmation resume, held-write resume, eval, workspace follow-up and screen action. The values are retry mode, screen context and its warnings, forced agent, user message id, the token and tool sinks, the abort token, and purge.
- **FR-004**: Each core package stack MUST be able to declare contributions: turn services, agent dependencies, REST-visible services, proactive jobs, data domains, screen resolvers and migrations path. The container MUST build its wiring by folding the core stacks and then the plugins.
- **FR-005**: Plugins MUST provide turn services by type and turn hooks as typed lists. A duplicate type MUST fail startup and name both providers. The reserved keys `memory_hooks` and `identity_builder` MUST be removed.
- **FR-006**: `settings` MUST reach readers as one type.
- **FR-007**: Core `Container.invoke`, `Container.resume`, `Container.from_config` and the core `_build_config` MUST be deleted. No turn entry point may remain in the core container.
- **FR-008**: `_build_config` (or its replacement) MUST NOT be called from outside the container.
- **FR-009**: The getters in `api/deps.py` that only return a container attribute MUST be replaced by typed attribute access. Routers MUST NOT reach `container.pool` for queries a store owns. (The routers that use the raw pool today are listed during planning.)
- **FR-010**: The plugin boundary test MUST also fail when plugin code reads a turn service by string key.
- **FR-011**: The production turn MUST run the turn extractor, with a regression test through the production container (keeping phase 198's test).
- **FR-012**: Behaviour MUST NOT change otherwise. The ze-api, ze-core, ze-automation and plugin suites MUST pass.

### Key Entities

- **Turn services**: the typed set of long-lived dependencies a turn can reach: stores, clients, judges, matchers, gates, resolvers, and the turn hooks contributed by plugins.
- **Turn request**: the typed set of values that belong to one turn: retry mode, screen context, forced agent, user message id, sinks, abort token.
- **Stack contribution**: what one core package or plugin declares to the container: services, agent dependencies, jobs, data domains, screen resolvers, migrations path.
- **Turn hook**: a plugin-provided step that runs at a fixed point of the turn, such as the contact-proposal hook after memory write.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 string-keyed service reads from `config["configurable"]` in source code, down from about 45 keys read across 26 files.
- **SC-002**: One config builder, down from two.
- **SC-003**: Adding a core service edits only its own package, down from up to six files today. Verified by the test in User Story 3.
- **SC-004**: `wiring/container.py` shrinks by at least half (from 793 lines). `ZeContainer` hand-lists no services; they come from the fold.
- **SC-005**: Every required service missing in a test build fails startup with its name: 100% of required fields covered by one parametrized test.

## Assumptions

- Phase 200 has landed, so child contexts are derived in one place. This phase changes where that place gets `tool_sink` and `script_runner` (from the turn request, not from string keys).
- The services value is passed in `config["configurable"]` under one key, per `langgraph-orchestration.md` ("dependencies arrive at invocation time"). That ADR still holds.
- Core packages stay non-plugins: they are not optional and they have an order. They gain the same contribution shape plugins have, not the plugin lifecycle.
- Out of scope:
  - narrowing the `ZePlugin` interface, deleting unused hooks, and moving late `startup()` binding into constructor injection (phase 210);
  - moving goal services off ze-personal (phase 211);
  - the turn module and confirmation registry (phase 207).
- The migrate meta-runner's `_ZE_*_VERSIONS` list may be replaced by stack contributions, if the fold makes it free. All 12 core chains are listed today, so there is no drift to fix.
- This is a pre-v1 hard cut: no compatibility key aliases.
