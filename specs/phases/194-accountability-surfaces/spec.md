# Feature Specification: Accountability Surfaces (B4)

**Feature Branch**: `194-accountability-surfaces`

**Created**: 2026-10-17 (refined through `/speckit-specify` 2026-10-18)

**Status**: Draft

**Input**: User description: "Accountability Surfaces (B4)": Maestro brief 2026-10-17, backend floor B4; overhaul plan section d, gaps 7, 8 and 11. Gap 13 (screen context on the trace) moved to phase 195 on 2026-10-17. The gaps logged while planning 185–190 (2026-10-17/18) are candidates, scoped by clarification.

**Governed by**: `PRODUCT.md` principle 4 ("Unattended work is accountable"), phases 135–136 (action-record ledger and instrumentation), 126–127 (contribution collisions), 182 (model tier on the trace), `specs/arch/pre-v1-hard-cuts.md`.

**Depends on**: nothing unfinished. Runs in parallel with the web phases. Feeds Doing (188: Runs, goal and workflow pages) and Governance (190) when it lands; neither blocks on it, and their pages are extended in a later web change.

**Doctrine functions served**: action (what Ze did on its own), governance (disagreements between the user and the executive are observable; the tier Ze runs is printed honestly).

**Owning packages** (for planning): ze-memory (ledger read), ze-collision (unchanged store), ze-api (routes), ze-worldstate (loops filter, if in scope), ze-onboarding (reset, if in scope). No migration expected.

## Context

Three small read surfaces sit over data that already exists, and none of them reaches the product API today:

1. **What Ze did (gap 7).** The action-record ledger holds every action Ze took, each citing the domain record it touched and the goal, workflow or run it served. No product route lists it.
2. **Disagreements (gap 8).** Contribution collisions (the executive and the user disagreeing, for example on a priority) are listed only on the developer/eval router.
3. **The configured tier (gap 11).** Each reply's trace shows which model tier ran. Governance cannot print the configured state: whether the light tier is on, its threshold, and which agents have a light model.

Planning phases 185–190 against the code logged further gaps. They are listed under Candidate gaps and scoped in by clarification.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See what Ze did, by goal, workflow or run (Priority: P1)

The user opens a goal, a workflow or a workspace run and sees the actions Ze took for it: what kind of action, who acted, whether it succeeded, what it touched and when. The same list across everything answers "what did Ze do while I was away".

**Why this priority**: Product principle 4. It is the main accountability surface and the one Doing is waiting for.

**Independent Test**: seed action records for two goals and one workflow run, then list by each subject, by time window and across all. Each list returns exactly the records that cite that subject, newest first, with plain fields.

**Acceptance Scenarios**:

1. **Given** action records citing goal G, **When** the user lists actions for goal G, **Then** only those records return, newest first, each with action kind, actor, lifecycle, outcome, summary, the record it touched and the time.
2. **Given** more records than one page, **When** the user lists them, **Then** the list pages with a cursor and never repeats or skips a record.
3. **Given** a time window, **When** the user lists actions since a time, **Then** only records that occurred after it return.
4. **Given** a subject with no records, **When** it is listed, **Then** the list is empty, not an error.

---

### User Story 2 - See disagreements in Governance (Priority: P2)

Governance lists the logged contribution collisions from the product API, the same data the eval tools read today.

**Why this priority**: governance visibility, small; the data and query exist.

**Independent Test**: the product route returns the same entries as the current eval route for the same filters, and the eval route no longer exists.

**Acceptance Scenarios**:

1. **Given** logged collisions, **When** Governance lists them with an entity, source or time filter, **Then** the matching entries return (limit at most 200).
2. **Given** the change has landed, **When** anything calls the old eval-only route, **Then** it is not found. The eval client uses the product route (pre-v1 hard cut, no copy kept).

---

### User Story 3 - Print the configured model tier honestly (Priority: P2)

Governance shows whether the light tier is on, the threshold under which a turn runs light, and, for each agent, its full model and light model.

**Why this priority**: the trace shows the tier per reply; without the configured state the reader cannot tell "light tier off" from "never chosen".

**Independent Test**: with the light tier on and off in config, the route reports the same values the routing step uses.

**Acceptance Scenarios**:

1. **Given** the shipped config (light tier on), **When** the route is read, **Then** it reports on, the threshold, and every agent with its full model and its light model or none.
2. **Given** the light tier is turned off in config and reloaded, **When** the route is read, **Then** it reports off with no restart.
3. **Given** any config, **When** the route is read, **Then** no secret appears in the response.

---

### User Story 4 - Candidate gaps (Priority: P3, scope set by clarification)

[NEEDS CLARIFICATION: which candidate gaps (below) join this phase? Recommended: the loops `since` filter and read-only channel status here; the component-to-call link and the screen-context resolver kinds go to a trace and screen-context follow-up (187b or a 195 follow-up).]

[NEEDS CLARIFICATION: the reset cascade bug: delete the personal-state reset (service, script and make target), fix it, or leave it? Recommended: delete. Nothing in the product uses it since 190, and `make db-reset` covers a developer's full wipe.]

### Edge Cases

- An action record whose touched record was later deleted still lists, with the reference shown as text.
- Records with the same timestamp page in a stable order (time, then id).
- A collision filter with a `since` after `until` returns an empty list, not an error.
- The tier route during a config reload returns either the old or the new values, never a mix.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST list action records over the product API, filterable by subject (goal, workflow, workflow run, workspace run), by a `since` time, and paged with a stable cursor, newest first. Each record shows action kind, actor, lifecycle, outcome, summary, the touched record's domain and id, and occurrence time.
- **FR-002**: The ledger read MUST live in the package that owns the ledger. The route only adapts it.
- **FR-003**: The collisions list MUST move from the eval router to the product API with the same filters and limits. The eval route MUST be removed and the eval client updated.
- **FR-004**: The system MUST report the configured tier state (light tier on or off, its threshold, and each agent's full and light model) from the same configuration the routing step reads, reflecting a config reload without restart, with no secrets.
- **FR-005**: Every new route MUST declare its response model, summary, description and operation id, and the generated web client MUST be regenerated.
- **FR-006**: Public docs MUST describe the three routes (native interface, memory, System One docs) and the phase row.
- **FR-007**: Candidate gaps in scope (per clarification) MUST each carry their own acceptance tests.

### Key Entities

- **Action record**: an action Ze took: kind, actor, producing plugin, lifecycle, outcome, summary, the authoritative record it touched, context (goal, workflow, run, message), time.
- **Collision**: a logged disagreement between two contributing functions over one entity.
- **Tier configuration**: light-tier switch, threshold, and per-agent full and light models.

### Candidate gaps (logged while planning 185–190)

- **Reset cascade (user decision 2026-10-18: log for 194).** The personal-state reset truncates its tables with cascade. It silently wipes every table that references them (open loops through goals, then their sources) without counting them in its preview. Its table lists predate phases 128–184, so sessions survive with their messages gone, and its full-dev scope always fails. Only a developer script and its make target still use it.
- **Component → tool call link (from 187).** Top-level message components carry no call index, so Ask's "Why?" opens the trace section by origin, not the exact call.
- **Loops `since` filter (from 186).** World's "Touched · 7 d" downloads every closed loop and filters in the browser.
- **Channel and Gmail connection status (from 190).** Governance › Connections omits it: no REST reports it.
- **Screen-context resolver kinds for cost anomalies, data domains and workspace files (from 190).** Governance publishes only its place and focused module.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each new surface has route tests for its filters, paging and empty case, and the action list returns only records that cite the requested subject (zero false inclusions in the seeded test).
- **SC-002**: No eval-only collisions route remains.
- **SC-003**: The tier route matches the routing step's configuration in 100% of the tested configs, including after a reload.
- **SC-004**: All Python suites, lint, and the web suites that consume the regenerated client pass.

## Assumptions

- The ledger already records the goal, workflow, workflow run and workspace run on each record's context, so subject filtering needs no new data. If a producer does not record its subject, its records are listed only in the unfiltered list.
- A new settings route is cleaner than extending the version route. The plan decides the exact path.
- Web pages that show these surfaces come later. 188 and 190 add the modules after this lands.
