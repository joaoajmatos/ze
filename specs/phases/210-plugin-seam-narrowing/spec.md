# Feature Specification: Plugin Seam Narrowing

**Feature Branch**: `210-plugin-seam-narrowing`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 201 (Typed turn services). The typed services object replaces the `config["configurable"]` string keys that `configurable_services()` feeds today.

**Input**: Architecture review 2026-10-22, candidate C14 plus plugin-audit findings #1 (wide seam), #2 (late services wired by monkey-patching) and #7 (retrieval policies named after plugin agents). Approved by the user ("go ahead with all of it").

## Context

`ZePlugin` (`core/contracts/ze-plugin/ze_plugin/plugin.py`, 233 lines) is a real seam with six adapters, one per plugin. But it is wide rather than deep: it has about 30 hook methods, and adding one agent takes about ten steps against the one that `plugin-agents.md` promises. Verified against the code on 2026-10-22:

- **Hooks with no plugin adapter.**
  - `agents()` (`plugin.py:43`) has no adapter and no consumer.
  - `jobs()` (`plugin.py:46`) has no consumer. `PersonalPlugin.jobs()` (`ze_personal/plugin.py:314`) returns four jobs that nothing reads, since the real registration is `register_proactive_jobs`.
  - `webhook_handlers` (consumed at `ze_api/wiring/webhooks.py:50`), `ingestion_fetchers` (`ze_ingestion/bootstrap.py:55`), `bundled_skill_paths` (`ze_skills/bootstrap.py:71`), `graph_nodes` and `graph_edges` (`ze_core/orchestration/graph.py:179-181`, `ze_api/wiring/workflow_graph.py:117-119`) each have a consumer but no plugin override.
  - `locale_data` has no override, but its default (`plugin.py:174-193`) loads the `locales/*.yaml` that five plugins ship. That behaviour is live and stays.
- **One object published under three keys.** A plugin publishes the same object through `agent_deps()` (keyed by type), `configurable_services()` (keyed by string) and `rest_stores()` (keyed by string). Examples: `news_store` in `ze_news/plugin.py:115-130`; `person_store` and `goal_store` in `ze_personal/plugin.py:217-269`.
- **Magic keys in a flat dict.** `configurable_services` carries `"identity_builder"` and `"memory_hooks"` (`ze_personal/plugin.py:256-266`), and it is merged with `dict.update` in two places (`ze_api/wiring/container.py:317`, `ze_core/container.py:55`). A second plugin returning the same key silently replaces the first.
- **Two ways to register a job.**
  - `register_proactive_jobs` is used by personal, messenger and prospecting.
  - `startup()` calls `container.proactive_scheduler.register` directly in news (`ze_news/plugin.py:229`), calendar (`ze_calendar/plugin.py:171`) and finance.
  - Messenger builds its poll job in `startup` (`ze_messenger/plugin.py:125-160`) and schedules it in `register_proactive_jobs`. This only works because the container calls `startup` first.
- **Late services wired by monkey-patching.** `startup(self, container: Any)` is an untyped back door that is used in both directions:
  - Plugins write private attributes onto the container (`container._calendar_reminder_job`, `ze_calendar/plugin.py:167`; `container._webhook_processor`, `ze_messenger/plugin.py:145`), and ze-api reads them back with `getattr` (`ze_api/wiring/hooks.py:138-157`).
  - ze-api patches plugin internals: `wire_plugin_consolidators` sets `consolidator._collision_store` and `_nli_client` (`hooks.py:127-134`), and `wire_plugin_loop_extractors` sets `.loop_extractor` (`hooks.py:137-157`).
  - Plugins patch their own objects after construction (`self._fetch_job._memory_store`, `ze_news/plugin.py:222-226`; `self.morning_briefing._news` and `._dream_store`, `ze_personal/plugin.py:324-336`).
  - Plugins find each other by guessing names. News looks for a `goal_store` attribute on any plugin (`ze_news/plugin.py:240-245`). Personal reads `news_store` out of other plugins' `configurable_services()` (`ze_personal/plugin.py:326`).
- **Retrieval policies named after plugin agents.**
  - `ze_memory/policies.py` (920 lines) holds twelve policy classes, ten of them near-copies (`CalendarPolicy:495`, `RemindersPolicy:537`, `EmailPolicy:567`, `ProspectingPolicy:632`, …).
  - Each plugin picks its policy in `memory_policies()`, keyed by the agent name as a string.
  - An unknown agent silently falls back to `CompanionPolicy` with a warning (`policies.py:902-919`).
  - Core thus knows plugin agents by name (Principle III).

Blast radius (`graphify affected ZePlugin --depth 2`): 183 nodes. That covers the six plugins, `ze_api/wiring/{container,agents,jobs,webhooks,screen,workflow_graph,hooks}.py`, `ze_core/container.py`, `ze_core/orchestration/graph.py`, `ze_ingestion/bootstrap.py`, `ze_skills/bootstrap.py`, and the plugin test suites.

The same back door exists in core: `wire_collision_detection` sets `memory_store._collision_store` and `correlation_engine._collision_store`/`_nli_client` (`hooks.py:120-125`). It is out of scope here; phase 212 (contribution submitter) owns it.

## User Scenarios & Testing *(mandatory)*

The users of this phase are the developer who writes a plugin or adds an agent, and Ze's user, whose plugins must keep working.

### User Story 1 - A plugin publishes a service once and every consumer finds it (Priority: P1)

A plugin author exposes one store. Agents, REST routes and per-turn graph nodes all receive it by type, and the author declares it in one place.

**Why this priority**: It removes the three-key duplication and the name-guessing between plugins. Stories 2 and 3 build on the same registry.

**Independent Test**: Build the container with two fake plugins. One provides `NewsStore`; the other declares a constructor dependency on `NewsStore`. The second receives the first's object. No `getattr` on plugins and no string key is involved.

**Acceptance Scenarios**:

1. **Given** a plugin that provides one object for type `T`, **When** the container starts, **Then** agents, REST dependencies and per-turn services resolve `T` to that object.
2. **Given** two plugins that both provide type `T`, **When** the container starts, **Then** startup fails with an error naming both plugins and `T`.
3. **Given** the news plugin and the personal plugin, **When** the morning briefing is built, **Then** it receives the news store and the dream store as constructor arguments, and no code writes `_news` or `_dream_store` after construction.

---

### User Story 2 - Jobs are declared, not registered from startup (Priority: P1)

A plugin lists its scheduled jobs: the job, the config key of its cron, the default cron, and the key that turns it on. ze-api schedules them all in one place, after every plugin's services exist.

**Why this priority**: It removes the hidden startup-before-register ordering rule and the second job path.

**Independent Test**: A fake plugin declares a job whose dependency is provided by another plugin. The job is scheduled once with the configured cron, and nothing calls `proactive_scheduler.register` from a plugin.

**Acceptance Scenarios**:

1. **Given** news, calendar, finance, messenger, personal and prospecting, **When** the container starts, **Then** every job they schedule today is scheduled with the same cron and enabled flag, and none is registered from `startup()`.
2. **Given** a job whose enabled key is false, **When** the container starts, **Then** it is not scheduled.
3. **Given** messenger, **When** the container starts, **Then** the inbound poll job is scheduled whatever order the plugins are started in.

---

### User Story 3 - Turn-level plugin behaviour is a typed observer, not a magic key (Priority: P2)

A plugin that wants to act after each turn (contact proposals today) or to add an identity block registers a typed turn hook. A second plugin can add its own hook without replacing the first.

**Why this priority**: Today a second `"memory_hooks"` silently replaces personal's contact hook. Phase 211 also needs this seam to take contact proposals out of ze-agents.

**Independent Test**: Two fake plugins each register a turn observer. After one turn both run, in plugin dependency order.

**Acceptance Scenarios**:

1. **Given** personal's contact proposal hook, **When** a turn ends, **Then** it runs through the typed observer list, and the `"memory_hooks"` and `"identity_builder"` keys no longer exist.
2. **Given** an observer that raises, **When** a turn ends, **Then** the error is logged with the plugin name and the other observers still run.

---

### User Story 4 - An agent declares its retrieval recipe (Priority: P2)

An agent author states which memory buckets to fetch, the limits, the token budget and whether to use the entity anchor, next to the agent's model. ze-memory runs one retriever over that recipe.

**Why this priority**: It takes plugin agent names out of core, removes about 700 lines of near-copies, and stops the silent fallback.

**Independent Test**: For each of the ten agents with a named policy today, the recipe run over the same seeded memory returns the same buckets in the same order as the old policy.

**Acceptance Scenarios**:

1. **Given** the calendar agent's recipe, **When** retrieval runs on seeded memory, **Then** the result equals what `CalendarPolicy` returned before the change.
2. **Given** an agent with no recipe, **When** the agent registers, **Then** registration fails with a message naming the agent, instead of falling back silently.
3. **Given** ze-memory's source, **When** it is searched for plugin agent names, **Then** none appear.

---

### User Story 5 - Unused hooks are gone (Priority: P3)

A plugin author reads a seam of a dozen hooks, each with at least one adapter or a live default.

**Why this priority**: This is the cheapest part, and it makes the seam honest. It can land first.

**Independent Test**: For every remaining hook on `ZePlugin`, at least one plugin overrides it or its default does live work. A test enforces this.

**Acceptance Scenarios**:

1. **Given** the new seam, **When** it is listed, **Then** `agents`, `jobs`, `webhook_handlers`, `ingestion_fetchers`, `bundled_skill_paths`, `graph_nodes` and `graph_edges` are absent, along with their consumers.
2. **Given** the five plugins that ship `locales/*.yaml`, **When** progress messages render, **Then** they are unchanged.

### Edge Cases

- A plugin provides an object under both a Protocol and its concrete class (today's `dep_map` has both `NLIClient` and `LocalNLIClient`). Consumers depend on the Protocol. Providing the concrete class as a separate key is an error unless a consumer needs the concrete class.
- A plugin is disabled by config (news off). Its jobs are not scheduled, its provided types are absent, and a consumer that declared the type as optional receives `None`, while one that declared it required fails at startup with a clear message.
- Two plugins depend on each other's provided types. This is a startup error naming the cycle, never a late-binding workaround.
- A plugin's `startup()` still has real async work to do (calendar replays unsent reminders). It keeps an optional `startup` that receives one typed runtime object with named fields, never the whole container.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `ZePlugin` MUST offer one typed provides registry, mapping a type to an object, in place of `agent_deps()`, `configurable_services()` and `rest_stores()`. Agents, REST dependencies and per-turn services MUST all resolve plugin objects from it by type.
- **FR-002**: A type provided by two plugins MUST fail startup with an error naming both plugins and the type.
- **FR-003**: `ZePlugin` MUST offer a declarative job list. Each entry gives the job, the cron config key, the default cron and the enabled config key. ze-api MUST schedule every entry after all plugins are constructed. Plugins MUST NOT call the scheduler from `startup()`.
- **FR-004**: `ZePlugin` MUST offer a typed list of turn observers and an optional typed identity contributor, in place of the `"memory_hooks"` and `"identity_builder"` keys. Observers from several plugins MUST all run.
- **FR-005**: Every service a plugin receives late today MUST arrive through its constructor before plugins are built: memory store, collision store, NLI client, loop extractor, admission-gate factory, scheduler, interface, channel registry and the providers of other plugins. No code outside a module MAY write its private attributes, and no plugin MAY find another by attribute name.
- **FR-006**: `wire_plugin_consolidators` and `wire_plugin_loop_extractors` MUST be deleted. The container MUST NOT carry plugin-set attributes (`_calendar_reminder_job`, `_webhook_processor`).
- **FR-007**: The optional `startup()` MUST receive one typed runtime object with named fields, not the container.
- **FR-008**: Each agent MUST declare a retrieval recipe: buckets, per-bucket limits, token budget and entity anchor on or off. ze-memory MUST run one retriever over recipes. The named policy classes and the `memory_policies()` hook MUST be deleted, and ze-memory MUST contain no plugin agent name.
- **FR-009**: An agent without a recipe MUST fail registration. The silent fallback to the companion policy MUST be deleted.
- **FR-010**: The hooks `agents`, `jobs` (and `PersonalPlugin.jobs`), `webhook_handlers`, `ingestion_fetchers`, `bundled_skill_paths`, `graph_nodes` and `graph_edges` MUST be deleted with their consumers. The `locale_data` default MUST keep loading `locales/*.yaml`.
- **FR-011**: A test MUST assert that every remaining `ZePlugin` hook has at least one plugin adapter or a default that does live work.
- **FR-012**: Behaviour for Ze's user MUST NOT change: same jobs on the same crons, the same REST responses, the same retrieved memory per agent and the same progress messages. This is a pre-v1 hard cut of the seam (Principle VIII), with no compatibility aliases.

### Key Entities

- **Plugin seam**: the interface a plugin implements. After this phase it has about a dozen hooks: provides, scheduled jobs, turn observers, identity contributor, agent module paths, migrations path, screen resolvers, signal sources, UI contributions, REST routes, channels, data domains, seed domains, integration types, onboarding, state extensions, pre-route node, checkpoint serde modules and an optional startup.
- **Provided service**: an object a plugin offers under a type. It is unique per type across all plugins.
- **Scheduled job declaration**: a job plus its cron key, default cron and enabled key.
- **Turn observer**: a plugin callback that runs after a turn with that turn's result and context.
- **Retrieval recipe**: an agent's declaration of what memory it needs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Adding an agent to an existing plugin takes at most 4 steps: write the agent and tools modules, list them in `agent_module_paths`, declare the recipe, add locale keys. Today it takes about 10.
- **SC-002**: No code in `apps/` or `plugins/` writes a private attribute of an object it does not own. A test greps for `._` assignments across the seam and finds none.
- **SC-003**: The seam has at most 20 hooks, down from about 30, and every one has an adapter or a live default.
- **SC-004**: `ze_memory/policies.py` shrinks by at least 600 lines, and retrieval equality tests pass for all ten former named policies.
- **SC-005**: `make test-py` passes, and every job scheduled before the change is scheduled after it with the same cron. A startup test compares the two lists.

## Assumptions

- Phase 201 lands first and provides the typed per-turn services object that the provides registry feeds.
- Plugin internals stay as they are ("plugins mature later"). Only how plugins meet the seam changes. Plugin refactors are queued separately.
- Moving automation's hooks and contacts out of ze-personal is phase 211, not this phase.
- `wire_collision_detection` (core stores) is phase 212's concern.
- `plugin-agents.md` already superseded `agents()`, so deleting it completes that ADR.
