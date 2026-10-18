# Feature Specification: Accountability Surfaces (B4)

**Feature Branch**: `194-accountability-surfaces`

**Created**: 2026-10-17 (refined through `/speckit-specify` 2026-10-18)

**Status**: Draft

**Input**: User description: "Accountability Surfaces (B4)": Maestro brief 2026-10-17, backend floor B4; overhaul plan section d, gaps 7, 8 and 11. Gap 13 (screen context on the trace) moved to phase 195 on 2026-10-17. Two gaps logged while planning 185–190 (loops `since`, channel status) and the reset deletion joined by clarification.

**Governed by**: `PRODUCT.md` principle 4 ("Unattended work is accountable"), phases 135–136 (action-record ledger and instrumentation), 126–127 (contribution collisions), 182 (model tier on the trace), `specs/arch/pre-v1-hard-cuts.md`.

**Depends on**: nothing unfinished. Runs in parallel with the web phases. Feeds Doing (188: Runs, goal and workflow pages) and Governance (190) when it lands; neither blocks on it, and their pages are extended in a later web change.

**Doctrine functions served**: action (what Ze did on its own), governance (disagreements between the user and the executive are observable; the tier Ze runs is printed honestly).

**Owning packages** (for planning): ze-memory (ledger read), ze-collision (unchanged store), ze-api (routes), ze-worldstate (loops filter), ze-personal / ze-google (channel status), ze-onboarding (reset deleted). One migration (`zc040`, ze-personal): planning found that poll failures are only logged, so "needs re-auth" needs the last poll outcome recorded.

## Context

Three small read surfaces sit over data that already exists, and none of them reaches the product API today:

1. **What Ze did (gap 7).** The action-record ledger holds every action Ze took, each citing the domain record it touched and the goal, workflow or run it served. No product route lists it.
2. **Disagreements (gap 8).** Contribution collisions (the executive and the user disagreeing, for example on a priority) are listed only on the developer/eval router.
3. **The configured tier (gap 11).** Each reply's trace shows which model tier ran. Governance cannot print the configured state: whether the light tier is on, its threshold, and which agents have a light model.

Planning phases 185–190 against the code logged further gaps. Where each went is listed under Logged gaps.

## Clarifications

### Session 2026-10-18 (user answers through the Maestro: all recommended)

- Q: Which logged gaps join 194? → A: The three core routes plus the loops `since` filter and read-only channel status. The component→call link and the screen-context resolver kinds go to trace and screen-context follow-ups (187b or a 195 follow-up).
- Q: The personal-state reset bug? → A: Delete `ResetService`, `scripts/reset_personal_state.py` and `make reset-personal-state`; `make db-reset` (+ seed) covers a developer's wipe.
- Q: Action list subjects? → A: Goal, workflow, workflow run and workspace run, plus `since`.

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
5. **Given** a workflow run that finished, **When** the user lists the workflow's actions, **Then** both its started and its finished records appear.

**Coverage limit**: goal-trace, workflow and workspace actions carry their subject. Calendar, reminder and prospecting actions carry only their own keys, so what Ze did through those tools during a goal or workflow run does not list under that goal or workflow. Pages must not promise it.

---

### User Story 2 - See disagreements in Governance (Priority: P2)

Governance lists the logged contribution collisions from the product API, the same data the eval tools read today.

**Why this priority**: governance visibility, small; the data and query exist.

**Independent Test**: the product route returns the same entries as the current eval route for the same filters, and the eval route no longer exists.

**Acceptance Scenarios**:

1. **Given** logged collisions, **When** Governance lists them with an entity, source or time filter, **Then** the matching entries return (limit at most 200).
2. **Given** the change has landed, **When** anything calls the old eval-only route, **Then** it is not found (pre-v1 hard cut, no copy kept). No eval client or tool calls it today; only the API tests move.

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

### User Story 4 - Closed loops by time (Priority: P2)

World's "Touched · 7 d" asks only for loops closed or dropped since a time, instead of downloading every closed loop and filtering in the browser.

**Why this priority**: small, and it removes an unbounded download from the home place.

**Independent Test**: seed closed loops across 30 days; listing closed loops since 7 days ago returns only those touched in the window.

**Acceptance Scenarios**:

1. **Given** closed and dropped loops across 30 days, **When** World lists both states since 7 days ago in one request, **Then** only loops whose last change falls in the window return.
2. **Given** no `since`, **When** loops are listed, **Then** the behaviour is unchanged.

---

### User Story 5 - Connection status in Governance (Priority: P3)

Governance › Connections shows each messaging channel and the Gmail connection, with its state (connected, needs re-auth, error, off) and when it last synced, read-only.

**Why this priority**: Governance omits it today; read-only and small.

**Independent Test**: with one connected Gmail channel and one channel whose credentials have expired, the route returns both with the right states and last-sync times, and no secret.

**Acceptance Scenarios**:

1. **Given** a connected Gmail channel, **When** the status is read, **Then** it reports connected with its last sync time.
2. **Given** expired credentials, **When** the status is read, **Then** it reports needs re-auth.
3. **Given** a poll that failed for another reason, **When** the status is read, **Then** it reports error.
4. **Given** a channel that receives mail by push (no polling), **When** the status is read, **Then** it reports unknown: "Receives by push; Ze does not monitor it." Ze sees no failures on that path, so it never claims connected.
6. **Given** a channel that has never polled successfully (a fresh install with an expired token), **When** its first poll fails, **Then** it appears in the status as needs re-auth, and the next successful poll still fetches mail from the normal lookback window (nothing is skipped).
7. **Given** a poll where some messages failed to fetch, **When** the status is read, **Then** it reports connected. Per-message failures are not counted in this phase.
5. **Given** any channel, **When** the status is read, **Then** no token or secret appears.

---

### User Story 6 - The broken reset is removed (Priority: P3)

The personal-state reset, which wipes tables it does not list, is deleted with its script and make target. A developer resets with the database reset.

**Why this priority**: removes a tool that destroys more than it reports (user decision).

**Independent Test**: no code, script, make target or doc refers to the reset service; the database reset target still works.

**Acceptance Scenarios**:

1. **Given** the cut, **When** the repository is searched, **Then** no reference to the reset service, its script or its make target remains outside history.
2. **Given** a developer, **When** they run the database reset and seed, **Then** they get a clean dev database as before.

### Edge Cases

- An action record whose touched record was later deleted still lists, with the reference shown as text.
- Records with the same timestamp page in a stable order (time, then id).
- A collision filter with a `since` after `until` returns an empty list, not an error.
- The tier route during a config reload returns either the old or the new values, never a mix.
- A Gmail token that is already dead at startup fails before Ze knows the account's address: the failure shows under the bare channel, keeps any known address, and the bare row disappears after the first successful poll once re-authorised, so the user sees one Gmail row.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The workflow-finished action MUST record its workflow, and the system MUST list action records over the product API, filterable by subject (goal, workflow, workflow run, workspace run), by a `since` time, and paged with a stable cursor, newest first. Each record shows action kind, actor, lifecycle, outcome, summary, the touched record's domain and id, and occurrence time.
- **FR-002**: The ledger read MUST live in the package that owns the ledger. The route only adapts it.
- **FR-003**: The collisions list MUST move from the eval router to the product API with the same filters and limits. The eval route MUST be removed (no eval client depends on it).
- **FR-004**: The system MUST report the configured tier state (light tier on or off, its threshold, and each agent's full and light model) from the same configuration the routing step reads, reflecting a config reload without restart, with no secrets.
- **FR-005**: Every new route MUST declare its response model, summary, description and operation id, and the generated web client MUST be regenerated.
- **FR-006**: Public docs MUST describe the three routes (native interface, memory, System One docs) and the phase row.
- **FR-007**: Loops MUST be listable by one or more states and a `since` time on their last change, without changing the unfiltered list.
- **FR-008**: The system MUST report each messaging channel's and the Gmail connection's state (connected, needs re-auth, error, off, or unknown for push channels and channels with no outcome yet) and last sync time over the product API, read-only, with no secrets. Recording an outcome MUST NOT move the sync position.
- **FR-009**: The personal-state reset service, its script and its make target MUST be removed, with every doc reference.

### Key Entities

- **Action record**: an action Ze took: kind, actor, producing plugin, lifecycle, outcome, summary, the authoritative record it touched, context (goal, workflow, run, message), time.
- **Collision**: a logged disagreement between two contributing functions over one entity.
- **Tier configuration**: light-tier switch, threshold, and per-agent full and light models.

### Logged gaps and where they went

- **Reset cascade → deleted here (User Story 6).** The personal-state reset truncates its tables with cascade. It silently wipes every table that references them (open loops through goals, then their sources) without counting them in its preview. Its table lists predate phases 128–184, so sessions survive with their messages gone, and its full-dev scope always fails. Only a developer script and its make target still use it.
- **Component → tool call link (from 187) → trace follow-up (187b), not here.** Top-level message components carry no call index, so Ask's "Why?" opens the trace section by origin, not the exact call.
- **Loops `since` filter (from 186) → here (User Story 4).** World's "Touched · 7 d" downloads every closed loop and filters in the browser.
- **Channel and Gmail connection status (from 190) → here (User Story 5).** Governance › Connections omits it: no REST reports it.
- **Screen-context resolver kinds for cost anomalies, data domains and workspace files (from 190) → screen-context follow-up, not here.** Governance publishes only its place and focused module.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each new surface has route tests for its filters, paging and empty case, and the action list returns only records that cite the requested subject (zero false inclusions in the seeded test).
- **SC-002**: No eval-only collisions route remains.
- **SC-003**: The tier route matches the routing step's configuration in 100% of the tested configs, including after a reload.
- **SC-004**: All Python suites, lint, and the web suites that consume the regenerated client pass.

## Assumptions

- Goal-trace, workflow and workspace producers record their subject on the record's context. The workflow-finished record gains its workflow id in this phase. Calendar, reminder and prospecting producers record no goal, workflow or run, and their records list only unfiltered or by their own domain.
- A new settings route is cleaner than extending the version route. The plan decides the exact path.
- Web pages that show these surfaces come later. 188 and 190 add the modules after this lands.
