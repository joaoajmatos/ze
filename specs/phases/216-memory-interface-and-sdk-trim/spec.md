# Feature Specification: Memory Interface and SDK Trim

**Feature Branch**: `216-memory-interface-and-sdk-trim`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 201 (Typed turn services), 210 (Plugin seam narrowing), 211 (Personal unbundling) and 212 (Contribution submitter).

- 210 deletes the retrieval policies, `memory_policies()` and the policy re-exports in `ze_sdk.memory`. It also gives plugins a typed provides registry, so a plugin can receive a memory service by type instead of importing the concrete class.
- 211 moves the contacts code and the workflow graph, which hold several of the callers this phase changes.
- 212 decides how the evidence lookups (facts, episodes, signals by id) are reached (its FR-006). This phase does not decide it again, and it removes the memory store's `_collision_store` patch together with 212.

**Input**: Architecture review 2026-10-22, candidate C16 ("Curate ze-memory's interface and trim ze-sdk"). Approved by the user ("go ahead with all of it"). The audit's constraint stands: do not split ze-memory into packages (`specs/arch/memory-package-split.md`).

## Context

ze-memory (`core/cognition/ze-memory`) is the store every agent reads from and every domain service writes to. Verified against the code on 2026-10-22, its interface is not the one callers use.

**Size.** 97 Python files and about 15,600 lines outside tests. The audit said about 14,000. Code outside the package imports 41 distinct `ze_memory` submodules (42 with the bare package). The biggest importers are ze-sdk (20 submodules), ze-api (18), ze-core (13), ze-automation (10), ze-worldstate (6) and ze-workspace (4).

**The `MemoryStore` Protocol is not the interface callers use.** `MemoryStore` (`ze_memory/store.py:54`) declares 11 methods: `retrieve`, `write_episode`, `propose_events`, `upsert_entity`, `get_entity`, `find_entity_by_name`, `upsert_task_state`, `get_task_state`, `get_profile`, `upsert_profile_facets` and `ingest_signal`. Callers outside ze-memory call at least 14 methods of `PostgresMemoryStore` (`retriever.py:158`) that are not on it:

| Method | Called from |
|---|---|
| `get_episodes_by_ids`, `get_facts_by_ids`, `get_signals_by_ids` | `ze_worldstate/extraction.py:221,227`; ze-personal `graph/memory_hooks.py:189,193`, `jobs/social_cooccurrence.py:150,154`; the correlation engine |
| `get_entities_by_ids` | `ze_api/api/deps.py:85`; the correlation engine |
| `pin_signals`, `list_recent_signal_ids` | the correlation engine; `ze_correlation/push.py` |
| `list_recent_facts`, `list_recent_episodes` | `ze_automation/jobs/goal_suggestion.py:54-55`; ze-news `preferences.py:144` |
| `count_unreviewed_facts` | ze-personal `jobs/briefing.py` |
| `get_session_summary` | `ze_core/orchestration/nodes/context.py:80` |
| `retract_fact_and_restore`, and the private `_retract_facts_matching` | ze-personal `agents/companion/tools.py:106,116` |
| `apply_policy_registry` | `ze_api/wiring/container.py:595` (deleted by 210) |
| `graph_store` | ze-personal `plugin.py:115` |

The audit said the Protocol "exposes `pool`". That is false: `pool`, `settings` and `graph_store` are on a second Protocol, `MemoryQueryable` (`store.py:17-38`), which only the retrieval policies use. `PostgresMemoryStore` exposes `pool` as a property (`retriever.py:185-191`). Inside ze-memory, the policies run raw SQL through it at 21 sites (`policies.py:280-817`), and `constraint_veto.py:342-344` and `relevance.py:273` read it with `getattr(store, "pool")`, falling back to `"_pool"`. No caller outside ze-memory uses `memory_store.pool`.

**Callers type the store as `Any`.** 31 parameters or fields are typed `memory_store: Any` (or `Any | None`) and 2 are typed `object`. Examples are `ze_agents/types.py:119`, `ze_core/container.py:38`, `ze_core/bootstrap.py:159`, five sites in `ze_worldstate/extraction.py`, `ze_correlation/engine.py:61`, `ze_automation/goals/planner.py:256`, ze-news `preferences.py:34` and `jobs/fetch.py:38`, and ze-personal `graph/memory_hooks.py:60,80,131`. About 11 sites use a real type.

**Code outside ze-memory reads and writes memory tables directly** with its own SQL on the shared pool:

| File | Tables |
|---|---|
| `ze_worldstate/store.py:274,335,352` | writes and reads `memory_relationships` |
| `ze_worldstate/rest.py:78-105` | `memory_facts`, `memory_episodes`, `memory_relationships`, `memory_entities` |
| `ze_core/conversation/sessions/store.py:93` | `memory_session_summaries` |
| ze-personal `contacts/consolidator.py:140`, `social/candidates.py:47-50`, `jobs/insights.py:70-86` | `memory_episodes`, `memory_relationships`, `memory_entities`, `memory_facts`, `memory_profile_facets` |
| `ze_api/api/v0/ui_modules/router.py:89` | `memory_entities` |
| `ze_seed/domains/memory.py` | inserts dev fixtures into five memory tables |

ze-api's memory router also passes `container.pool` into `ze_memory.admin`.

**Private attributes written from outside.** `hooks.py:36` sets `automation.goal_store._memory_store`, and `hooks.py:123` sets `shared.memory_store._collision_store` (phase 212 removes the second).

**ze-sdk re-exports memory internals wholesale.** `ze_sdk/memory.py` exports 48 names, including the concrete `PostgresMemoryStore` and `PostgresDreamStore`, `build_admission_gate`, `extract_facts` and nine policy classes. 18 of them are imported by nothing: `CommitmentChoice`, `Episode`, `Procedure`, `RetrievalRequest`, `fact_to_contribution`, `candidate_from_action_pattern`, `ProcedureAdmissionService`, `ProcedureActivator`, `ProcedureDiscovery`, `intersect_tools`, `format_procedure_guidance`, `ProcedureCandidate`, `PostgresDreamStore` and the five dream types. `MemoryContext` is imported only by tests, which makes 19. The boundary test (`packages/ze-sdk/tests/test_plugin_boundaries.py`) bans plugins from importing `ze_memory`, but `ze_sdk.memory` hands them the same objects, so the ban is cosmetic.

The rest of ze-sdk has the same problem. Exported names that nothing imports:

| Module | Exported | Unused |
|---|---|---|
| `automation` | 23 | 23 |
| `types` | 8 | 8 |
| `errors` | 31 | 29 |
| `contribution` | 24 | 11 |
| `__init__` | 19 | 5 |
| `channels` | 13 | 10 |
| `screen` | 15 | 4 |
| `onboarding` | 9 | 4 |
| `proactive` | 11 | 3 |
| `ui` | 8 | 3 |

**Plugins bypass ze-sdk for the contract packages.** Plugin code imports `ze_agents` directly on 104 lines in 50 files, and `ze_logging` on 46 lines. ze-sdk already re-exports `get_logger`, but one site uses it. The boundary test bans `ze_core`, `ze_api`, `ze_plugin` and `ze_memory`, not `ze_agents` or `ze_logging`. AGENTS.md says "Plugin code imports from `ze_sdk.*`", so the written rule and the enforced rule disagree.

**Stale ADR.** `memory-package-split.md` puts the package at `packages/ze-memory`, lists `propose_facts` on the Protocol (removed in phase 134) and lists `ze_core.*` as dependencies.

**Blast radius.** `graphify affected PostgresMemoryStore --depth 2` returns 244 nodes: ze-api 20, ze-personal 16, ze-core 10, ze-news 3, ze-messenger 3, finance, calendar and ze-sdk 1 each, and 182 test nodes. (`MemoryStore` has no unique graph node.)

**Doctrine function.** Memory: one record that every function reads through one interface.

## Clarifications

### Session 2026-10-22

- Q: Which direction for ze-sdk: enforce it as the only plugin surface, or trim it and allow plugins to import the contract packages directly? → A: Trim. ze-sdk exports only names plugins use from packages they may not import directly. Plugin code may import the contract and kernel packages (`ze_agents`, `ze_logging`) directly. AGENTS.md and the boundary test are rewritten to agree.
- Q: How wide is the memory interface work? → A: One `MemoryStore` Protocol that matches what callers use, with no `pool`, typed callers and no `memory_*` SQL outside ze-memory. Per-sub-domain interfaces are deferred.

## User Scenarios & Testing *(mandatory)*

The users of this phase are developers who read or write memory from another package or a plugin. Ze's user sees no change.

### User Story 1 - The memory Protocol is the interface callers use (Priority: P1)

A developer who needs memory reads one Protocol and finds every operation callers use on it, typed. They never need the concrete class, a private method or the pool.

**Why this priority**: Every caller today depends on `PostgresMemoryStore` through an `Any`, so a renamed method fails only at runtime, and a test double cannot tell which methods it must provide.

**Independent Test**: A type check over the repository passes with every `memory_store` parameter typed by the Protocol, and a test asserts that `PostgresMemoryStore` satisfies it.

**Acceptance Scenarios**:

1. **Given** the code outside ze-memory, **When** it calls a method on the memory store, **Then** that method is on the Protocol.
2. **Given** the Protocol, **When** it is read, **Then** it has no `pool`, no private method and no `apply_policy_registry`.
3. **Given** a `memory_store` parameter or field anywhere in the repo, **When** it is read, **Then** it is typed by a memory Protocol, not `Any` or `object`.
4. **Given** the companion's forget tool, **When** it retracts a fact, **Then** it calls one public method, and nothing outside ze-memory calls `_retract_facts_matching`.

---

### User Story 2 - Memory tables are read and written only by ze-memory (Priority: P1)

A developer who changes a memory table's schema changes ze-memory alone. No other package holds SQL against `memory_*` tables.

**Why this priority**: Nine files in four packages hold their own SQL against memory tables, including writes to `memory_relationships` from ze-worldstate. A schema change in ze-memory breaks them silently.

**Independent Test**: A test scans every package except ze-memory (and the ze-seed fixtures, see Assumptions) and finds no SQL against a `memory_*` table. The open-loop, World, insight and contact behaviour that used that SQL is unchanged.

**Acceptance Scenarios**:

1. **Given** an open loop linked to an entity, **When** the loop's relationships are written or read, **Then** ze-worldstate calls the memory interface, and the stored rows are the same as before.
2. **Given** the loop REST detail, the insights job and the contacts consolidator, **When** they run on seeded memory, **Then** they return the same results as before.
3. **Given** ze-api's memory admin route, **When** it runs, **Then** ze-memory receives no raw pool from the route.

---

### User Story 3 - ze-sdk exports only what plugins use, and the import rule matches the test (Priority: P2)

A plugin author reads ze-sdk and finds only names that some plugin uses. The rule in AGENTS.md says exactly what the boundary test enforces.

**Why this priority**: 19 unused memory names and about 100 unused names elsewhere make ze-sdk look like a curated surface when it is a pass-through. Re-exporting concrete memory classes makes the `ze_memory` ban meaningless.

**Independent Test**: A test lists every name ze-sdk exports and fails if one is imported by no plugin. The boundary test and the AGENTS.md import rule name the same allowed packages.

**Acceptance Scenarios**:

1. **Given** `ze_sdk.memory`, **When** it is read, **Then** it exports no concrete store class, no policy class and no name that no plugin imports.
2. **Given** a plugin that needs the memory store, the dream store or the admission gate, **When** it is built, **Then** it receives the object by its Protocol through the provides registry (210), not by importing a concrete class from ze-sdk.
3. **Given** AGENTS.md's import rule, **When** it is compared with `test_plugin_boundaries.py`, **Then** both allow and forbid the same packages.

---

### User Story 4 - The memory ADR matches the code (Priority: P3)

A developer who opens `memory-package-split.md` reads the package's real location, Protocol and dependencies.

**Why this priority**: Documentation only, but the ADR is the first place a new reader looks.

**Independent Test**: Every path, method and dependency the ADR names exists in the code.

**Acceptance Scenarios**:

1. **Given** the ADR, **When** it is read, **Then** it names `core/cognition/ze-memory`, the Protocol as it is after this phase, and ze-memory's real dependencies.

### Edge Cases

- **The retrieval policies** (`MemoryQueryable`, 21 raw-SQL sites in `policies.py`) are deleted or replaced by 210's single retriever. This phase does not touch them. If 210 has not landed, this phase waits for it.
- **Evidence lookups by id** (`get_facts_by_ids`, `get_episodes_by_ids`, `get_signals_by_ids`) are decided by 212's FR-006: either on the Protocol or read by the submitter's evidence resolver. This phase follows that decision. Callers outside the resolver that still need them (ze-api `deps.py`, the correlation engine) get them from the Protocol.
- **ze-worldstate writes into `memory_relationships`** by design: open loops reuse the memory graph (phase 109). The loop edges go through `GraphStore` methods, which ze-memory owns, rather than a second graph.
- **A plugin needs a type, not a service** (`Signal`, `EntityRef`, `Entity`, `Relationship`, `WORKS_ON`). Plain types and constants stay exported from `ze_sdk.memory`.
- **Tests that mock methods the store does not have** (`submit_perception_facts` ×11 in ze-core tests, `propose_facts` in ze-ingestion tests). They are fixed to mock the Protocol, so a double can no longer offer a method the real store lacks.
- **Splitting ze-memory into several packages** is out of scope (`memory-package-split.md`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `MemoryStore` Protocol MUST declare every method that code outside ze-memory calls on the memory store, with typed parameters and results. It MUST NOT declare `pool`, `settings`, private methods or wiring methods.
- **FR-002**: `PostgresMemoryStore` MUST satisfy the Protocol, and a test MUST check it.
- **FR-003**: Every `memory_store` parameter, field and constructor argument in the repo MUST be typed by the Protocol (or a narrower memory Protocol), never `Any` or `object`.
- **FR-004**: Fact retraction with restore MUST be one public method on the Protocol. No code outside ze-memory MAY call a private memory-store method.
- **FR-005**: No code outside ze-memory MAY write a private attribute of the memory store, or set the memory store on another object's private attribute (`hooks.py:36`). Each consumer MUST receive it through its constructor.
- **FR-006**: No package other than ze-memory MAY hold SQL that reads or writes a `memory_*` table, except the dev fixtures in ze-seed. Each affected caller MUST go through the memory interface, with the same results. A test MUST enforce it.
- **FR-007**: No caller MAY hand ze-memory a raw pool from outside its constructor (`ze_memory.admin` from the memory router).
- **FR-008**: `ze_sdk.memory` MUST export only plain types, constants and Protocols that at least one plugin imports. It MUST NOT export concrete stores (`PostgresMemoryStore`, `PostgresDreamStore`), policy classes, or service functions (`build_admission_gate`, `extract_facts`). Plugins MUST receive those services by Protocol through the provides registry (210).
- **FR-009**: Every other ze-sdk module MUST export only names that at least one plugin imports. A test MUST fail on an exported name that no plugin imports.
- **FR-010**: Plugin code MAY import the contract and kernel packages `ze_agents` and `ze_logging` directly. It MUST NOT import `ze_core`, `ze_api`, `ze_plugin` or `ze_memory`, and reaches anything else it needs through ze-sdk. The import rule in AGENTS.md and `test_plugin_boundaries.py` MUST state exactly this list. ze-sdk MUST NOT re-export `get_logger` or other names from the packages plugins may import directly.
- **FR-011**: `memory-package-split.md` MUST be corrected: package location, Protocol and dependencies.
- **FR-012**: Ze's user MUST see no behaviour change: the same retrieval, World, loop details, insights, contacts and briefing. Pre-v1 hard cut (Principle VIII): removed names get no aliases.

### Key Entities

- **Memory interface**: the Protocol(s) that other packages use to read and write memory.
- **Plugin surface**: the names ze-sdk exports for plugin authors.
- **Boundary rule**: the list of packages plugin code may and may not import, written in AGENTS.md and enforced by one test.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 calls from outside ze-memory to a memory-store method that the Protocol lacks, down from at least 14 distinct methods.
- **SC-002**: 0 `memory_store` parameters typed `Any` or `object`, down from 33.
- **SC-003**: 0 files outside ze-memory and the ze-seed fixtures hold SQL against `memory_*` tables, down from 8.
- **SC-004**: 0 names exported by ze-sdk that no plugin imports, down from about 120 (19 in `ze_sdk.memory`).
- **SC-005**: `make test-py`, `make test-pg` and the memory and contacts eval scenarios pass with no regression.

## Assumptions

- 210, 211 and 212 have landed. The policy classes, `MemoryQueryable`, `apply_policy_registry` and the memory store's `_collision_store` patch are already gone.
- ze-seed's memory fixtures may keep direct inserts, because they build dev data below the interface on purpose. They are listed by name in the test's allowed set.
- ze-memory keeps its internal module layout. Narrower per-sub-domain interfaces (facts, episodes, signals, graph, procedures, action records, dream) are out of scope and deferred.
- The 41 submodules that outside code imports are not reduced by this phase, except where a caller moves to the Protocol.
- ze-eval keeps no Ze dependencies and is not affected.

