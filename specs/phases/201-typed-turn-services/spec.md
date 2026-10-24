# Feature Specification: Typed Turn Services

**Feature Branch**: `201-typed-turn-services`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 200

**Governed by**: `specs/arch/langgraph-orchestration.md` (dependencies arrive at invocation time in `config`, never in graph state), phase 47b (plugin dependency map), phase 49 and 64 (plugins reach the engine only through `ze_sdk`), phase 76 (ze-api shell and per-package bootstrap), `specs/arch/pre-v1-hard-cuts.md`, `specs/GLOSSARY.md` (Turn, Thread).

**Doctrine functions served**: governance (what a turn can reach is declared and checked at startup, and a missing service is an error, not a silent skip), action (every turn path, conversation, workflow step or inbound message, runs with the services it declares).

**Owning packages** (for planning): ze-core (`container.py`, `bootstrap.py`, every reader under `orchestration/` and `conversation/turn.py`), ze-api (`wiring/container.py`, `wiring/agents.py`, `wiring/webhooks.py`, `api/deps.py`, `api/eval/router.py`, `api/ws/{turns,confirmation,rollback_state,commands}.py`), ze-plugin (`ZePlugin.configurable_services`), ze-automation (`bootstrap.py` workflow graph config, `graph/routing_context.py`), ze-worldstate, ze-memory and ze-skills (their stacks and readers), ze-personal (`graph/workflow.py`, `graph/memory_hooks.py`, `plugin.py`), ze-sdk (boundary test). No migration, no REST or WS change.

**Input**: Architecture review 2026-10-22, candidate C2. A typed `TurnServices` and a `TurnRequest` replace the string keys in `config["configurable"]`. The container folds contributions from each core package's `*Stack`. Plugins provide services by type. Delete the core `Container.invoke`/`resume`/`from_config` and the duplicate `_build_config`.

## Context

This is a deepening refactor. Its users are the maintainers who add a service to Ze, and the plugin authors whose graph code reads services. The guarantee it protects is one the user sees: every part of a turn that should run does run, and a missing service is an error at startup, not a silent no-op.

Every graph node and several plugins reach their dependencies through `config["configurable"]`, an untyped dictionary keyed by strings. Facts checked on 2026-10-22:

- **Three builders that disagree.** The core `Container._build_config` (`core/engine/ze-core/ze_core/container.py:51-69`) and `ZeContainer._build_config` (`apps/ze-api/ze_api/wiring/container.py:314-360`) build the dictionary separately, and the ze-api one does not call the core one. The core builder sets `turn_extractor`; the ze-api builder does not. In production, `write_memory`'s turn extractor (`ze_core/orchestration/nodes/memory.py:225`) therefore never runs, so no events or entity proposals come from conversation turns (bug B2; phase 198 patches it). The third builder is the workflow graph's: `configure_workflow_executor` writes its own nine-key dictionary (`core/automation/ze-automation/ze_automation/bootstrap.py:272-283`). The workflow graph runs the engine's nodes, so a workflow step runs without `budget_checker` (the spend budget never holds a step), `skill_matcher`, `tier_judge`, `system_one_client`, `commitment_intake`, `fact_extractor`, `turn_extractor`, `nli_client` and every plugin service (`person_store`, `memory_hooks`, `identity_builder`). The code does not say which of these omissions are deliberate.
- **Keys nobody reads.** Eight keys that `ZeContainer._build_config` sets have no reader in source: `interface`, `loop_store`, `loop_graph_store`, `loop_entity_resolver`, `loop_surfacer`, `workspace_client`, `workspace_gate` and `workspace_store`. (An earlier draft said `workflow_scheduler` was read but never set. That was wrong: the workflow graph's own builder sets it, `bootstrap.py:281`, and `load_workflow_step` reads it, `ze_personal/graph/workflow.py:62`.)
- **About 45 distinct keys.** They are read from files in ze-core (13 files), ze-api (4), ze-automation (3), ze-personal (2), ze-plugin, ze-worldstate, ze-memory and ze-skills (1 each). Plugins read keys that ze-api sets: `memory_hooks.py:38-42` reads `person_store`, `contact_channel_store`, `collision_store`, `nli_client` and `memory_store`; `graph/workflow.py` reads `workflow_store`, `openrouter_client`, `settings`, `workflow_planner` and `procedure_admission`. These reads get around the plugin boundary test (`packages/ze-sdk/tests/test_plugin_boundaries.py`), which checks imports, not string keys.
- **One key, two shapes.** `settings` is sometimes a dictionary and sometimes an object. Each reader handles both (`nodes/memory.py:312,327,353`, `nodes/context.py:255,335`, `nodes/preprocessing.py:27`, `nodes/correlation.py:98,107`, `conversation/turn.py:161`).
- **Magic merges.** Plugin services are merged with `dict.update` in both builders (`ze_core/container.py:55`, `wiring/container.py:317`). `memory_hooks` and `identity_builder` are reserved keys inside that flat dictionary (`ze_personal/plugin.py:258-268`). A second plugin returning `memory_hooks` silently replaces the first.
- **Private calls from outside.** `_build_config` is private, but `api/eval/router.py:106` and `api/ws/confirmation.py:130` call it.
- **Per-turn values mixed with services.** `retry_mode`, `retry_replaces`, `screen_context`, `screen_context_invalid`, `forced_agent`, `user_message_id`, `reporter`, `token_sink`, `tool_sink`, `pre_approved_writes` and `abort_token` arrive as extra keys in the same dictionary as long-lived services (`eval/router.py:59-64`, `ws/turns.py:123-143`, `:556`, `ws/confirmation.py:386`, `conversation/turn.py:256,476`, `ws/rollback_state.py:24`, `nodes/execution.py:268-273`).
- **Cancel does not reach a WS turn (bug B15, found 2026-10-22; phase 198 fixes it).** Only core `Container.invoke` creates an `AbortToken` and registers it for `abort_invocation` (`ze_core/container.py:111-113`). `invoke_raw_turn` creates none, so `execute_tool` reads `abort_token` as `None` (`nodes/execution.py:302`). The web app's Cancel sends the `cancel` command (`RetryControl.tsx:31`), `ws/commands.py:41` calls `abort_invocation`, and it finds no token: the running agent loop is never stopped. Cancel only drops the pending confirmations and the telemetry recorder.
- **No locality for a new service.** A new core service is registered by hand in up to six places: a `ZeContainer` field (65 fields today), the constructor call (`wiring/container.py:646-724`), a `_build_config` key, a getter in `api/deps.py` (30 `get_*` functions), an entry in `build_dep_map` (`wiring/agents.py:63-110`), and the job, data-domain, screen or migration lists. `container.py` is the most-changed file in the repo; phases 184, 185, 192, 194, 195 and 197 each edited it.
- **A second entry point that is not dead.** The review called core `Container.invoke` (`ze_core/container.py:71`), `resume` (`:167`) and `from_config` (`:218`) unused, with only core tests calling them. That is wrong for `invoke`: the inbound webhook dispatcher calls `container.invoke(prompt, thread_id)` in production for every inbound message that passes the sender filter (`ze_api/wiring/webhooks.py:140-155`; the dispatcher gets the `ZeContainer` at `wiring/container.py:726`). That path runs without the thread lock and without turn telemetry, and it handles a parked write with its own fourth confirmation style: `send_confirmation` and no pending row. `resume` has no production caller. `ZeContainer` overrides `from_config` (`wiring/container.py:424`). `abort_invocation` (`ze_core/container.py:158`) is used by the WS cancel command. The test module the review named (`tests/test_container_invoke.py`) does not exist.
- **Stacks already exist.** Seven core packages already return a `*Stack` from their `bootstrap.py`: `EngineStack`, `WorldstateStack`, `CorrelationStack`, `WorkspaceStack`, `IngestionStack`, `SkillsStack`, `AutomationStack`. They have no common contribution shape.

**Blast radius** (graphify, 2026-10-22):
- `_build_config`: 7 source and 6 test references, all in ze-api.
- `ZeContainer`: 6 source and 10 test references in ze-api.
- Every orchestration node in ze-core reads `config["configurable"]`, and so do the plugin and core readers listed above.
- `make_graph_input` callers: see phase 200.

## Clarifications

### Session 2026-10-22

- Q: Which services does a workflow step get? → A: Today's subset, typed. Each service a workflow step goes without is declared absent with its reason, and the list is handed to phase 214 (unattended step runner), which decides the behaviour. The missing spend budget (`budget_checker`) is flagged for 214 (FR-014).
- Q: The inbound webhook turn uses core `Container.invoke`. Where does it move? → A: Phase 207. This phase deletes `resume`, `from_config` and the core `_build_config`. `invoke` stays until phase 207 makes the inbound message a turn-module adapter that persists and asks for confirmations like the WS path (FR-007).
- Q: Where is B15 (Cancel never stops a WS turn) fixed? → A: Phase 198 fixes it now: `invoke_raw_turn` creates and registers the abort token. This phase folds the token into the turn request and keeps 198's regression test (FR-013).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A turn's services are typed and complete (Priority: P1)

A maintainer writes or changes a graph node. It reads its dependencies as typed attributes of one turn-services value. A service that a deployment may leave out is an explicit optional field. A required service that is missing stops startup with an error naming it.

**Why this priority**: The missing `turn_extractor` (B2) and the never-set `workflow_scheduler` show that today's dictionary fails silently. A maintainer cannot see what a turn can reach without reading two builders and every plugin.

**Independent Test**: Build the production container with one required service missing: startup fails and names it. Build it complete: a contract test lists every service a node reads, and asserts that each is a field of the turn services and is non-null where it is required.

**Acceptance Scenarios**:

1. **Given** the production container, **When** a conversation turn runs, **Then** the turn extractor runs (B2 cannot recur).
2. **Given** a workflow run is cancelled, **When** the next step loads, **Then** the cancellation check reads the scheduler from the typed services, as it reads it from the workflow graph's own dictionary today.
3. **Given** a node test, **When** it is written, **Then** it passes a typed fake turn-services value rather than a hand-built dictionary.
4. **Given** `settings`, **When** any node reads it, **Then** it gets one type; no reader branches on a dictionary or an object.

---

### User Story 2 - Per-turn values are a separate request (Priority: P1)

A caller that starts or resumes a turn (WebSocket message, Retry, confirmation resume, eval, workspace follow-up, inbound message) passes one typed turn-request value: retry mode, screen context, forced agent, user message id, the reporter, and the sinks and abort token for this turn. It never edits the services dictionary.

**Why this priority**: Callers today reach into a private builder (`eval/router.py:106`, `ws/confirmation.py:130`) to add string keys, and the eval path sets keys the product path does not.

**Independent Test**: Every turn entry point builds a turn request. A grep finds no `_build_config` call outside the container, and no string-keyed per-turn value.

**Acceptance Scenarios**:

1. **Given** a Retry, **When** the turn starts, **Then** `retry_mode` arrives through the turn request and every write gate sees it.
2. **Given** an eval turn with a forced agent and a screen context, **When** it runs, **Then** both arrive through the same turn request the WebSocket path uses.
3. **Given** the user presses Cancel while a reply is running, **When** the cancel command arrives, **Then** the running agent loop stops, through the abort token in the turn request. (Phase 198 fixes the bug first; this phase moves the token into the turn request.)

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

The core container's `resume` and `from_config`, and its duplicate `_build_config`, are deleted. Its `invoke` stays only for the inbound webhook turn, until phase 207 replaces it, and it builds its services and turn request the same way as every other entry point. Tests move to the production entry point, or are deleted.

**Why this priority**: The second path holds a second config builder and a fourth confirmation style that readers mistake for the real one.

**Independent Test**: The core container has no config builder and no `resume` or `from_config`. The ze-core suite passes through `invoke_raw_turn`/`resume_turn` with a test container. The only remaining caller of `invoke` is the webhook dispatcher.

**Acceptance Scenarios**:

1. **Given** the engine package, **When** a maintainer looks for how a conversation turn starts, **Then** there is one function to read, and `invoke` is marked as the inbound-message path that phase 207 replaces.
2. **Given** an inbound message passes the sender filter, **When** its turn runs, **Then** it reads the same typed services as a WS turn.

---

### Edge Cases

- **Workflow graph.** The workflow graph runs with its own state extension and today its own nine-key dictionary. Its nodes read the same typed services type, `workflow_scheduler` becomes a typed field, and each service a workflow step goes without today stays absent, declared with its reason (FR-014).
- **Inbound messages.** An inbound message turn starts from the webhook dispatcher with no socket. It builds a turn request like any other caller, and keeps today's delivery and confirmation behaviour until phase 207's adapter replaces it.
- **Optional deployments.** With no workspace sidecar, no System One client or no commitment intake, the field is `None`, and the reader handles `None` explicitly, as it does today. The difference is that `None` is declared, not accidental.
- **LangGraph checkpoints.** Services are invocation-time values (`langgraph-orchestration.md`) and must never be checkpointed. The turn services value lives in `config`, not in graph state.
- **Plugin ordering.** Services contributed by a plugin that another plugin needs at construction stay in the existing topological plugin order. Late binding through `startup()` is phase 210's concern, not this phase's.
- **Tests that build configs by hand.** Dozens of tests write `{"configurable": {...}}`. They move to a test helper that builds a typed fake.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Graph nodes, the workflow graph and plugin graph code MUST read services from one typed turn-services value. Reading a service by string key from `config["configurable"]` MUST NOT remain anywhere in source code.
- **FR-002**: Each service MUST be a declared field: required (non-null at startup) or optional (explicitly `None` when absent). Startup MUST fail with the service name when a required service is missing.
- **FR-003**: Per-turn values MUST travel in a separate typed turn request, built by every turn entry point: WebSocket message, Retry, confirmation resume, held-write resume, eval, workspace follow-up and screen action. The values are retry mode, screen context and its warnings, forced agent, user message id, retry replaces, the progress reporter, the token and tool sinks, step pre-approvals, and the abort token.
- **FR-004**: Each core package stack MUST be able to declare contributions: turn services, agent dependencies, REST-visible services, proactive jobs, data domains, screen resolvers and migrations path. The container MUST build its wiring by folding the core stacks and then the plugins.
- **FR-005**: Plugins MUST provide turn services by type and turn hooks as typed lists. A duplicate type MUST fail startup and name both providers. The reserved keys `memory_hooks` and `identity_builder` MUST be removed.
- **FR-006**: `settings` MUST reach readers as one type.
- **FR-007**: Core `Container.resume`, `Container.from_config` and the core `_build_config` MUST be deleted. Core `Container.invoke` MUST remain only as the inbound webhook path, MUST build its services and turn request like every other entry point, and is deleted by phase 207.
- **FR-008**: `_build_config` (or its replacement) MUST NOT be called from outside the container.
- **FR-009**: The getters in `api/deps.py` that only return a container attribute MUST be replaced by typed attribute access. Routers MUST NOT reach `container.pool` for queries a store owns. (The routers that use the raw pool today are listed during planning.)
- **FR-010**: The plugin boundary test MUST also fail when plugin code reads a turn service by string key.
- **FR-011**: The production turn MUST run the turn extractor, with a regression test through the production container (keeping phase 198's test).
- **FR-012**: Behaviour MUST NOT change otherwise, apart from FR-011. The ze-api, ze-core, ze-automation and plugin suites MUST pass.
- **FR-013**: Every turn entry point MUST create the turn's abort token as part of the turn request, so the WS cancel command stops a running turn. Phase 198's B15 regression test MUST stay.
- **FR-014**: The workflow graph MUST read the same typed turn-services type as a conversation turn, with today's subset. Every service a workflow step does not get today MUST be declared absent for that kind of run, with the reason. This phase MUST NOT add services to workflow steps; the declared list is the input to phase 214.
- **FR-015**: Keys that no reader uses MUST NOT become fields.

### Key Entities

- **Turn services**: the typed set of long-lived dependencies a turn can reach: stores, clients, judges, matchers, gates, resolvers, and the turn hooks contributed by plugins.
- **Turn request**: the typed set of values that belong to one turn: retry mode and the reply it replaces, screen context and its warnings, forced agent, user message id, reporter, sinks, step pre-approvals, abort token.
- **Stack contribution**: what one core package or plugin declares to the container: services, agent dependencies, jobs, data domains, screen resolvers, migrations path.
- **Turn hook**: a plugin-provided step that runs at a fixed point of the turn, such as the contact-proposal hook after memory write.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 string-keyed service reads from `config["configurable"]` in source code, down from about 45 keys read in 24 source files.
- **SC-002**: One config builder, down from three.
- **SC-003**: Adding a core service edits only its own package, down from up to six files today. Verified by the test in User Story 3.
- **SC-004**: `wiring/container.py` shrinks by at least half (from 793 lines). `ZeContainer` hand-lists no services; they come from the fold.
- **SC-005**: Every required service missing in a test build fails startup with its name: 100% of required fields covered by one parametrized test.

## Assumptions

- Phase 198 has fixed B2 (turn extractor) and B15 (abort token) with regression tests. Phase 200 has landed, so child contexts are derived in one place. This phase changes where that place gets `tool_sink` and `script_runner` (from the turn request, not from string keys).
- The services value is passed in `config["configurable"]` under one key, per `langgraph-orchestration.md` ("dependencies arrive at invocation time"). That ADR still holds.
- Core packages stay non-plugins: they are not optional and they have an order. They gain the same contribution shape plugins have, not the plugin lifecycle.
- Out of scope:
  - narrowing the `ZePlugin` interface, deleting unused hooks, and moving late `startup()` binding into constructor injection (phase 210);
  - moving goal services off ze-personal (phase 211);
  - the turn module and confirmation registry, and deleting `Container.invoke` with an inbound-message adapter (phase 207);
  - which services an unattended workflow step should get, including the missing spend budget (phase 214).
- The migrate meta-runner's `_ZE_*_VERSIONS` list may be replaced by stack contributions, if the fold makes it free. All 12 core chains are listed today, so there is no drift to fix.
- This is a pre-v1 hard cut: no compatibility key aliases.
