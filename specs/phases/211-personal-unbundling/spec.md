# Feature Specification: ze-personal Unbundling

**Feature Branch**: `211-personal-unbundling`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 210 (Plugin seam narrowing). This phase uses its provides registry, turn observers and declarative jobs. It also uses 201's per-stack contributions for core packages.

**Input**: Architecture review 2026-10-22, candidate C15 plus ze-api audit #5 (goals reach the shell through ze-personal) and plugin-audit findings #3 (ze-personal does four jobs) and #5 (contacts hard-wired into the core agent contract). Implements `specs/arch/person-identity.md`. Approved by the user ("go ahead with all of it").

## Context

`ze-personal` (`plugins/ze-personal`) should hold persona, the companion and research agents, and the briefing and insight jobs. Verified 2026-10-22, it also does three other jobs.

**1. ze-automation's plugin face.** `PersonalPlugin` (`ze_personal/plugin.py`, 388 lines; it imports ze-automation, ze-priority, ze-news and ze-correlation at lines 10-36) declares ze-automation's parts:

- the goal pre-route node `inject_goal_routing_context` (`:297-300`);
- `WorkflowAgentState` as the state extension (`:271-274`);
- `ze_automation.workflow.types` serde (`:276-280`);
- memory policies for the goals, workflow and planner agents (`:282-295`);
- `goal_store` and `goal_executor` as REST stores (`:232-240`);
- `PostgresGoalStore` and `GoalTitleProvider` as agent deps (`:217-230`).

ze-api reaches goals only through `container._plugin_stores`:

- `api/v0/goals/router.py:50,84,150,188,224-225`
- `api/ws/turns.py:272`
- `api/ws/goal_actions.py:37-38,276-277`
- `ze_seed/context.py:24-30`

The workflow execution graph (`ze_personal/graph/workflow.py`, 793 lines, still labelled "Transitional location") is imported by `ze_api/wiring/workflow_graph.py:33`. Remove ze-personal and goal routes, goal-aware routing and gate redirects break.

**2. The messaging-hub store library.** `UserChannelStore`, `ChannelWatermarkStore` and `ThreadChannelMap` (`ze_personal/channels/`) are built by ze-api (`wiring/stores.py`) and injected back into the plugin. Their real consumer is ze-messenger (`plugin.py`, `inbound/processor.py`, `jobs/inbound_poll.py`, `agents/messenger/{agent,tools}.py`), plus ze-api's channels router (`api/v0/channels/router.py`).

**3. The contacts library.** Calendar (`agents/calendar/agent.py`), messenger (`agents/messenger/agent.py`, `inbound/processor.py`) and prospecting (`agents/{agent,tools}.py`) depend on ze-personal only for contacts: extractors, `PersonStore`, `Person` and `ContactChannelStore`. Contacts also reach into the core agent contract:

- `AgentResult.contact_proposals` (`ze_agents/types.py:209`)
- `contacts_context` and `AgentContext.contacts` (`types.py:52,106`)
- `BaseAgent._format_contacts` (`base_agent.py:231-269`)

**Two smaller problems:**

- **Outreach detection runs in the companion.** The companion runs an English-only outreach regex on every turn (`companion/agent.py:263,287`) and calls the prospecting tool `log_outreach_event` through an `OutreachLog` Protocol it defines (`companion/outreach_log.py`). Prospecting imports that Protocol (`ze_prospecting/plugin.py:9`), so the dependency points the wrong way.
- **Goal state rules are written twice, differently.** The screen action (`api/ws/goal_actions.py:207-231`) refuses to pause a goal that is not active or awaiting a gate, and refuses to abandon a completed or abandoned goal. The agent tools `pause_goal` and `abandon_goal` (`ze_automation/agents/goals/tools.py:230-240,323-334`) check nothing.

**Three ids for one person** (`person-identity.md`):

- `contacts.id`;
- the memory-graph `person` entity;
- `uuid5(name)` for relationship ranking (`ze_priority/scoring.py:110-116`).

The contact contribution sends the contacts id as `entity_ids`.

Blast radius: `graphify affected PersonalPlugin --depth 2` (19 nodes, mostly tests). The import edges are wider:

- ze-api has 13 import sites into `ze_personal.channels`, `contacts` and `graph.workflow`;
- messenger has 11, prospecting 4 and calendar 1;
- ze-seed reads `_plugin_stores`.

## User Scenarios & Testing *(mandatory)*

The users of this phase are Ze's user, whose goals, contacts and channels must keep working, and the developer who changes automation, contacts or messaging without touching ze-personal.

### User Story 1 - Goals belong to ze-automation end to end (Priority: P1)

The goal routes, the goal WS actions, goal-aware routing, gate redirects and the workflow graph all reach goals through ze-automation's own typed stack. Nothing goes through ze-personal or a string-keyed dict.

**Why this priority**: It removes a core-through-plugin dependency, and today the goal REST routes break if ze-personal is absent.

**Independent Test**: Start the container with ze-personal not installed. The goal REST routes, a goal gate redirect and a workflow run all work.

**Acceptance Scenarios**:

1. **Given** the container without ze-personal, **When** `GET /api/v0/goals` is called, **Then** it returns the user's goals.
2. **Given** a goal awaiting a gate, **When** the user replies in chat, **Then** goal-aware routing sends the reply to the goal agent as it does today.
3. **Given** the code base, **When** it is searched for `_plugin_stores`, **Then** nothing is found.
4. **Given** a scheduled workflow, **When** it runs, **Then** the workflow graph comes from ze-automation and its state extension and serde are registered by ze-automation.

---

### User Story 2 - One set of goal rules for chat and screen (Priority: P1)

Pausing, resuming, abandoning, and approving or stopping at a gate follow the same rules whether the user does it from the Doing page or asks in chat.

**Why this priority**: Today the agent can "pause" a completed goal, which the screen refuses. This is a user-visible inconsistency.

**Independent Test**: For each goal state, the tool and the screen action return the same outcome for pause, resume, abandon and gate approve/stop.

**Acceptance Scenarios**:

1. **Given** a completed goal, **When** the user asks Ze in chat to pause it, **Then** Ze says it is already finished, and the goal's status does not change.
2. **Given** an active goal, **When** the user abandons it from the screen and then asks in chat to abandon it, **Then** the second request says it is already abandoned.

---

### User Story 3 - Contacts are their own package (Priority: P2)

Calendar, messenger, prospecting and personal depend on a contacts package. They do not depend on each other or on the companion.

**Why this priority**: It explains most of the odd dependency edges, and it lets core stop knowing about contacts.

**Independent Test**: The dependency check shows no plugin depending on ze-personal. Contacts still appear in agent prompts, and contact proposals from a calendar turn still reach the contact review queue.

**Acceptance Scenarios**:

1. **Given** a turn in which the calendar agent mentions a new attendee, **When** the turn ends, **Then** a contact proposal reaches the review queue through a contacts turn observer. `AgentResult` has no `contact_proposals` field.
2. **Given** an agent prompt, **When** it is built, **Then** the known-people block comes from a prompt section that the contacts package contributes, and ze-agents has no `contacts` field or `_format_contacts`.
3. **Given** the user says "I emailed Ana about the proposal", **When** the turn ends, **Then** prospecting's own observer logs the outreach, the companion has no outreach code, and `OutreachLog` no longer exists.

---

### User Story 4 - One id per person (Priority: P2)

Ana is the same person in contacts, in the memory graph, in relationship nudges and in collision checks, and renaming her does not split her.

**Why this priority**: It implements `person-identity.md` and fixes collision checks that compare ids from two different spaces.

**Independent Test**: Create a contact, rename it, and trigger a relationship nudge. All three records carry one entity id.

**Acceptance Scenarios**:

1. **Given** a new contact, **When** it is created, **Then** it references exactly one memory-graph `person` entity. If that entity is missing, it is created.
2. **Given** a relationship nudge for Ana, **When** it is ranked, **Then** its id is Ana's entity id, and `uuid5(name)` is not used anywhere.
3. **Given** Ana renamed to "Ana S.", **When** the rename is saved, **Then** the entity's name and the contact's name change, and no id changes.

---

### User Story 5 - Channel stores live with their owner (Priority: P3)

The user's connected channels, their watermarks and the thread-to-channel map are owned by the messaging package, which is their real consumer.

**Why this priority**: It is lower risk and mostly a move, but it finishes the separation.

**Independent Test**: Governance › Connections lists channels with their status, and inbound polling runs. No import of `ze_personal.channels` remains.

**Acceptance Scenarios**:

1. **Given** a connected Gmail channel, **When** the poll job runs, **Then** the watermark advances exactly as before.
2. **Given** `GET /api/v0/channels/status`, **When** it is called, **Then** it returns the same response as before.

### Edge Cases

- **Existing contacts with no graph entity.** A migration creates the missing entities and links them. Pre-v1, the local database may be wiped and reseeded instead (Principle VIII). The plan picks one approach and says which.
- **Two contacts that point to the same entity** (duplicate people). Uniqueness is enforced from now on. The migration merges the duplicates into the reviewed contact, or flags them for review if neither is reviewed.
- **ze-messenger disabled.** The channels status route still answers, with an empty list and no error, because the stores live with the routes' owner. Which package owns them is the open question below.
- **The workflow graph imports `ze_sdk`.** ze-automation cannot depend on ze-sdk, because ze-sdk depends on ze-automation. The moved module therefore imports from the core contracts directly (`ze_agents`, `ze_memory`), as core packages do.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: ze-automation MUST contribute its own pre-route node, state extension, checkpoint serde modules, retrieval recipes for its agents, and goal and workflow services, through the core stack contribution shape from phase 201. It MUST NOT become an entry-point plugin.
- **FR-002**: The workflow execution graph MUST move from `ze_personal/graph/workflow.py` into ze-automation. ze-api MUST import it from there.
- **FR-003**: `ZeContainer._plugin_stores` and `collect_plugin_stores` MUST be deleted. Goal routes, WS goal actions, the WS turn path and ze-seed MUST reach goals through the typed automation stack.
- **FR-004**: The goal lifecycle rules MUST live in one ze-automation module that both the goal agent tools and the WS screen actions call: pause, resume, abandon, and gate approve and stop, with their status preconditions. The two copies MUST give the same outcome for every goal state.
- **FR-005**: A contacts package MUST own `PersonStore`, `ContactChannelStore`, the contact types, extractors, consolidator, tools, screen resolvers, migrations and data domains. ze-personal, ze-calendar, ze-messenger and ze-prospecting MUST depend on it, and none of them may depend on ze-personal.
- **FR-006**: `AgentResult.contact_proposals`, `AgentContext.contacts`, the `contacts_context` prompt argument and `BaseAgent._format_contacts` MUST leave ze-agents. Contact proposals MUST travel through a contacts turn observer (210), and the known-people block MUST come from a prompt section the contacts package contributes.
- **FR-007**: Outreach detection MUST move to a prospecting turn observer. `OutreachLog` and the companion's outreach code MUST be deleted.
- **FR-008**: Each person MUST be one memory-graph `person` entity. A contact MUST reference exactly one entity, and an entity MUST have at most one contact. Relationship ranking, priority items and contact contributions MUST use the entity id, and `uuid5(name)` MUST be removed from `ze_priority/scoring.py`.
- **FR-009**: `UserChannelStore`, `ChannelWatermarkStore`, `ThreadChannelMap` and the channel types MUST move to the messaging owner, together with their tables' migration ownership.
- **FR-010**: After this phase ze-personal MUST depend on neither ze-automation nor ze-priority. It may keep ze-news only for the briefing's news read, and may read goals through a provided type rather than an import.
- **FR-011**: Ze's user MUST see no behaviour change: the same goals, contacts, channels, prompts, briefing and REST responses. This is a pre-v1 hard cut with no re-export shims (Principle VIII).

### Key Entities

- **Person**: someone in the user's life. Exactly one memory-graph entity (glossary).
- **Contact**: a person's address-book record (aliases, relationship, channels). It references one person entity.
- **Goal lifecycle rules**: the allowed status changes for a goal and what each one requires.
- **User channel**: an account through which Ze receives the user's messages, with its watermark and last poll outcome.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `PersonalPlugin`'s constructor takes at most 10 injected services, down from about 20.
- **SC-002**: No package under `plugins/` other than ze-personal itself imports `ze_personal`, and ze-api imports only `ze_personal.persona`.
- **SC-003**: For every goal status, the agent tool and the screen action agree on pause, resume, abandon and gate actions, as shown by one table test.
- **SC-004**: Every person appears under one id in contacts, the graph and relationship ranking, as shown by a test-pg check.
- **SC-005**: `make test-py` passes. The routing, contacts and companion eval scenarios pass with no regression.

## Assumptions

- Phase 210's provides registry, turn observers and job declarations exist.
- Phase 201's core stack contribution shape exists.
- `package-reorg.md` §4 put contacts and goals in ze-personal. Phase 74 already moved the automation types out, so this phase completes phase 74 rather than reversing it.
- The data-export double counting is fixed separately in phase 217, which depends on this phase.

## Open Questions

- Which package owns the user channel stores? The default in FR-009 is ze-messenger. The alternative is the contacts package or ze-communication, if channel status must answer while messenger is disabled. The plan decides, and records why.
