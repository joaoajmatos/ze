# Feature Specification: Claim Honesty Fixes

**Feature Branch**: `199-claim-honesty-fixes`

**Created**: 2026-10-22

**Status**: Implemented

**Wave**: 0 of the architecture review 2026-10 (`specs/README.md`, phases 198–219). Runs in parallel with 198 (Audit Bug Fixes). 203 (Open-Loop Lifecycle) depends on this phase.

**Input**: Implement four accepted ADRs exactly: [user-statement-provenance](../../arch/user-statement-provenance.md) (bug B7), [loop-claim-kind-from-state](../../arch/loop-claim-kind-from-state.md) (B12), [executive-licence](../../arch/executive-licence.md) (B8) and [suspected-loop-resolution](../../arch/suspected-loop-resolution.md) (B3). Each fix starts with a failing test through the real interface, against a real Postgres (test-pg) where SQL is involved. B7 includes a one-time data-repair migration.

## Context

Ze labels every claim it stores with a **claim kind** (fact, suspicion, priority, …) and a **provenance** (where it came from: `prompt_supplied`, `live_search`, `graph_recall`, `synthesized`). The labels drive behaviour: decay, retrieval contamination rules, the posture World draws, and the licence check on the contribution seam (`claim-topology.md`, `contribution-seam.md`). Four labels are wrong today. The user decisions are settled in the four ADRs (D1–D4); this phase does not reopen them.

**Doctrine functions served**: Perception (honest provenance on what it reads), Memory (stated beliefs keep their standing), Executive (licence, loop claim kind, loop resolution).

### What the code does today (verified 2026-10-22)

| Bug | Where | What happens |
|---|---|---|
| B7 | `ze_core/orchestration/nodes/memory.py:217`, `ze_ingestion/sink.py:53`, `ze_messenger/inbound/processor.py:207` | Facts perception extracts from a conversation turn, an ingested document or an inbound message are stamped `synthesized`. |
| B7 | `ze_memory/dream/promoter.py:237-282` | The nightly dream pass lowers every uncorroborated `synthesized` fact older than 30 days by 0.03 a night. Below 0.50 it clears `reviewed`; below 0.25 it sets `contradicted`. Expiry also contradicts `synthesized` facts past `valid_until`. Neither checks who wrote the fact. |
| B7 | `ze_personal/contacts/types.py:16-22`, `contacts/consolidator.py:239`, `graph/memory_hooks.py:221`, `ze_prospecting/agents/tools.py:50`, `ze_personal/jobs/social_cooccurrence.py:53` | Contact proposals from email and calendar carry `live_search`, but every stored contact and contact source is written `synthesized`, because the consolidator never copies the proposal's provenance. Co-occurrence hypothesis evidence from email and calendar is labelled `live_search`. |
| B7 | `ze_memory/consolidation_store.py:81` (`insert_merged_fact`), `consolidator.py:183` | When consolidation merges two near-duplicate facts with the model, it writes the merged fact `synthesized`, claim kind `fact`, with no dream run. Two merged user statements then read as Ze's own conclusion. A dream insight merged with a user fact reads as a fact. |
| B12 | `ze_worldstate/store.py:406` (`stamp_declared`), `:512` (`promote`), `extraction.py:354/462`, `tracking.py:130` | A loop's claim kind is written once at creation. Confirming or promoting a suspected loop leaves it `suspicion`, so World draws a confirmed loop as a dotted hunch (`ze_priority/compose/rules.py:77`) and `PriorityItem.claim_kind` (`scoring.py:51`) carries the stale kind. |
| B8 | `ze_plugin/contribution.py:52-62` | Executive is licensed for identity, fact, inference, suspicion and priority. The doctrine allows priority and suspicion only. |
| B3 | `ze_worldstate/store.py:26-32`, `extraction.py:380-400`, `admission.py:113-117` | "That's done" looks for a matching suspected, active or drifting loop and moves it to `closed`. The transition table has no `suspected → closed` edge, so the store raises; the inflow catches it and logs `loop_extraction_failed`. The suspected loop stays in Needs you. A resolve on an active loop records no resolving evidence. |

### Audit claims that turned out false or incomplete

- **`memory_facts` has no `creation_method` column.** Only `memory_relationships` has one (`zm003`). The ADR says decay and expiry "also check `creation_method`" and that the repair selects facts "whose `creation_method` is `extracted` or `explicit`". Neither can be done as written (see FR-005 and Clarifications).
- **The dream promoter's fact insert names that missing column** (`promoter.py:191-199`). Promoting a synthesized insight raises, which fails morning integration; decay and expiry run after the promotion loop, so they are skipped on any night with a promotion.
- **Contacts from email and calendar are not stored as `live_search`.** The proposal is; the stored row is `synthesized` (dataclass default). Contacts from conversation and from prospecting web research are also stored `synthesized`.
- **The inbound-message extractor** (`ze_messenger/inbound/processor.py:207`) was not named in the audit; it stamps `synthesized` too.
- **Consolidation's merge writer** (`consolidation_store.py:81`) was not named in the audit or in this spec's first draft; the facts-lane review found it (2026-10-23). It stamps every merged fact `synthesized`. Separately, `docs/memory.md:271` says reviewed facts are never auto-merged, but `fetch_active_facts` does not filter on `reviewed` (outside this phase).
- **Decay never updates `updated_at`**, so `delete_contradicted_facts` (`consolidation_store.py:110`) can hard-delete a fact soon after decay contradicts it. Those facts cannot be restored. A fact's `reviewed` value before decay cleared it is recorded nowhere.
- Minor: `claim_tone` lives in `ze_components/claims.py`, not `compose/rules.py`; the loop posture is built at `compose/rules.py:77`, not `:74`.

### Measured impact (local `ze` database, 2026-10-22)

311 facts. 2 are `synthesized` and were not written by the dream (both `agent=companion`, `claim_kind=inference`, not contradicted). 0 carry the decay signature. 1 dream run has ever been recorded. 4 contacts, all `synthesized`; 0 contact sources. The repair is cheap here; the code fix is what matters, because every new fact from conversation would start to decay after 30 days.

### Blast radius (`graphify affected`, depth 2)

- `OpenLoop`: `ze_priority/compose/rules.py` (`_loop_posture`, `_loop_card`, `mention_card`), `ze_priority/scoring.py` (`score_loop`), `ze_worldstate` (`rest.py`, `screen_resolvers.py`, `contribution.py`, `extraction.py`, `tracking.py`), REST `apps/ze-api/ze_api/api/v0/loops/schemas.py`, test builders (`apps/ze-api/tests/pg/_builders.py`, `ze-priority/tests/factories.py`) and about 15 ze-worldstate test modules. Web readers of the REST `claim_kind` field: `pages/world/lib/concerns.ts:73`, `widgets/loops-rail/ui/LoopsRail.tsx:44`, `pages/doing-goal/ui/DoingGoalPage.tsx:165`.
- `_close_matching_loop`: `_commit_admitted`, `propose_loop_candidates`, `admission.py`; tests `test_extraction.py`, `test_contribution.py`, `apps/ze-api/tests/pg/test_loop_evidence.py`.
- `submit_perception_facts`: `nodes/memory.py`, `ze_ingestion/sink.py`, `ze_messenger/inbound/processor.py`, `ze_onboarding/persistence.py`, companion `remember_fact`, `ze_automation/goals/learning.py`; re-exported by `ze_sdk/memory.py`.
- `_run_confidence_decay`: only `run_morning_integration`.
- `_LICENSE`: read only by `validate_and_submit` in `ze_plugin/contribution.py`; producers submitting as Executive are `ze_worldstate/contribution.py` and `ze_priority/contribution.py` (priority and suspicion only).

## Clarifications

### Session 2026-10-22

- Q: `memory_facts` has no `creation_method`. How do dream decay and expiry recognise a fact the dream wrote? → A: By `dream_run_id IS NOT NULL` (the promoter always sets it). No schema change. The promoter's insert stops naming `creation_method`. The Maestro corrects the ADR's wording on main.
- Q: What does the data repair restore on facts that decay damaged? → A: Nothing. It re-stamps only. It counts the facts that carry the decay signature and reports the count; it does not change their confidence, `reviewed` or `contradicted`.
- Q: How far does the contact fix go? → A: A contact source's provenance follows from its source type: manual, conversation, email and calendar give `prompt_supplied`; research (prospecting web research) gives `live_search`. A new contact takes the provenance of the source that created it. Co-occurrence evidence from email or calendar becomes `prompt_supplied`. A one-time re-stamp of `contacts` and `contact_sources` runs on the `zc` chain (ze-personal).
- Q: (default, accepted) What does the loops REST response say for a dropped loop's claim kind? → A: `null`; the field becomes nullable and `@myguyze/ze-client` is regenerated.
- Q: (default, accepted) Which migrations? → A: `zm026` (fact re-stamp), `zw006` (drop `open_loops.claim_kind`), and the next free `zc` number for the contact re-stamp.
- Q: (default, accepted) How does a resolve get the `suspected → closed` edge? → A: Through its own loop-store method (`suspected`, `active` or `drifting` → `closed`; links the resolving evidence; never writes a fingerprint). The generic transition table does not change.

### Session 2026-10-23

- Q: Consolidation merges near-duplicate facts and stamps the result `synthesized` with no dream run. How is a merged fact stamped? → A: (architect decision, delegated by the Maestro; option a) A merged fact carries the provenance and claim kind its two inputs share. Consolidation merges two facts only when neither is a dream insight and both have the same provenance and claim kind; otherwise it leaves both as they are. FR-002 and zm026 do not change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - What the user says stays believed (Priority: P1)

The user tells Ze "I'm vegetarian". Ze stores it as something the user supplied. Weeks later, with no other mention, Ze still holds it at the same standing. It is not lowered night by night, not un-reviewed, and not marked contradicted. The same holds for facts Ze reads from the user's documents, mailbox and calendar. Only Ze's own dream insights decay and expire.

**Why this priority**: This is the bug with real cost. Every fact the user states in conversation starts to decay after a month and is marked contradicted about 19 nights later, which breaks the doctrine rule that stated beliefs outrank inferred ones.

**Independent Test**: Against test-pg, store a fact through each perception path (conversation turn, ingestion sink, inbound message), age it past 30 days, run the dream integration step several times, and read the fact back. Separately, store a dream insight and check that it still decays and expires.

**Acceptance Scenarios**:

1. **Given** a conversation turn whose fact admission persists a fact, **When** the fact is written, **Then** its provenance is `prompt_supplied` and its claim kind is `fact`.
2. **Given** an ingested document and an inbound email that yield facts, **When** they are written, **Then** each fact's provenance is `prompt_supplied`.
3. **Given** a perception fact created 60 days ago, uncorroborated, **When** the dream integration step runs ten times, **Then** its confidence, `reviewed` and `contradicted` are unchanged.
4. **Given** a dream insight created 60 days ago, uncorroborated, **When** the integration step runs, **Then** its confidence drops by 0.03 per run, and it is contradicted after `valid_until` passes, as today.
5. **Given** a perception fact that was (wrongly) stored `synthesized` with a `valid_until` in the past, **When** expiry runs, **Then** it is not contradicted.
6. **Given** a dream run that promotes an insight, **When** morning integration runs, **Then** the insight is stored and decay and expiry still run that night.
7. **Given** two near-duplicate `prompt_supplied` facts that consolidation merges, **When** the merged fact is written, **Then** it is `prompt_supplied`, claim kind `fact`, with no dream run.
8. **Given** a dream insight and a perception fact that say the same thing, **When** consolidation runs, **Then** it does not merge them and both rows are unchanged.

---

### User Story 2 - Existing facts are re-stamped once (Priority: P1)

After the upgrade, facts perception already wrote with the wrong label carry the right one, so decay never touches them again. Facts that decay already damaged are counted and reported, not changed.

**Why this priority**: Without the repair, every fact stored before the fix keeps the wrong label. The local database has 0 facts with the decay signature, so restoring them is not worth a reconstruction rule.

**Independent Test**: On test-pg, insert rows that match each case below, run the repair, and compare. Run it twice; the second run changes nothing.

**Acceptance Scenarios**:

1. **Given** a fact stored `synthesized` with no dream run, **When** the repair runs, **Then** it is `prompt_supplied` and its claim kind is `fact`.
2. **Given** a dream insight (`synthesized`, written by a dream run), **When** the repair runs, **Then** it is unchanged.
3. **Given** a perception fact that decay drove below 0.25 and contradicted, **When** the repair runs, **Then** it is re-stamped, its confidence, `reviewed` and `contradicted` are unchanged, and it is counted in the repair's report.
4. **Given** facts already `prompt_supplied`, `live_search` or `graph_recall`, **When** the repair runs, **Then** they are unchanged.

---

### User Story 3 - A loop's standing follows its state (Priority: P1)

The user confirms a suspected loop on World, or a second independent source promotes it. From then on World draws it as a priority, not a dotted hunch, and every reader (ranking, composed answers, REST, the screen resolver) reports `priority`.

**Why this priority**: A confirmed concern drawn as a guess tells the user Ze did not hear them.

**Independent Test**: Against test-pg, create a suspected loop, confirm it (REST and `confirm_loop`), promote another through corroboration, and read each through the store, `PriorityView`, the composed posture and `GET /api/v0/loops`.

**Acceptance Scenarios**:

1. **Given** a suspected loop, **When** it is read, **Then** its claim kind is `suspicion`.
2. **Given** a suspected loop, **When** the user confirms it, **Then** its claim kind reads `priority` everywhere, with no write to a claim-kind field.
3. **Given** a suspected loop, **When** corroboration promotes it to active, **Then** its claim kind reads `priority`.
4. **Given** loops in `active`, `drifting` and `closed`, **When** they are read, **Then** their claim kind is `priority`.
5. **Given** a dropped loop, **When** a reader asks for its claim kind, **Then** it has none (REST returns `null`), and World draws no posture for it.
6. **Given** the upgraded database, **When** a maintainer looks at `open_loops`, **Then** the `claim_kind` column is gone.

---

### User Story 4 - "That's done" closes a loop nobody confirmed (Priority: P1)

The user says "I sent Ana the budget" and Ze had only suspected that loop. The loop moves to `closed`, the turn or email that resolved it is recorded on the loop, and it leaves Needs you. No error is logged.

**Why this priority**: Today the resolve silently fails and the stale loop keeps asking the user for attention.

**Independent Test**: Against test-pg, create a suspected loop, run a conversation turn (commitment intake) and an email (loop gate) that resolve it, and read the loop and its evidence back.

**Acceptance Scenarios**:

1. **Given** a suspected loop, **When** a conversation turn resolves it, **Then** it is `closed`, `closed_at` is set, and the turn's evidence is linked to it.
2. **Given** a suspected loop, **When** an email or an ingested document resolves it, **Then** it is `closed` with that evidence linked. **When** a calendar event resolves it, **Then** it is `closed` with nothing linked (the calendar inflow carries no evidence).
3. **Given** an active or drifting loop, **When** an inflow resolves it, **Then** it is `closed` with the resolving evidence linked.
4. **Given** a suspected loop, **When** the REST close route, the `close_loop` tool, decay or the drift sweep try to move it to `closed`, **Then** the move is refused as today.
5. **Given** a resolve, **When** it closes a loop, **Then** no dismissed-evidence fingerprint is written.

---

### User Story 5 - Executive cannot state facts (Priority: P2)

A contribution submitted as Executive with claim kind fact, inference or identity is refused before anything is written. Priority and suspicion contributions from Executive pass as today.

**Why this priority**: The licence is the seam's main promise. No producer breaks it today, so this closes a door rather than fixing a visible bug.

**Independent Test**: Submit one contribution per claim kind as Executive through the real seam with a write callback that records calls.

**Acceptance Scenarios**:

1. **Given** an Executive contribution with claim kind `fact`, `inference` or `identity`, **When** it is submitted, **Then** it raises `UnlicensedClaimKindError` and the write callback never runs.
2. **Given** an Executive contribution with claim kind `priority` or `suspicion`, **When** it is submitted, **Then** it is written.
3. **Given** the loop producers and the priority-override producer, **When** their existing tests run, **Then** they pass unchanged.

---

### User Story 6 - Contacts carry where they came from (Priority: P3)

A contact Ze learned from the user's email, calendar or conversation is labelled as supplied by the user's own sources. A contact Ze found by researching the web is labelled `live_search`.

**Why this priority**: No behaviour reads contact provenance for decay today; the label shows in posture and in collision records.

**Independent Test**: Against test-pg, run the consolidator on proposals from each source type, and the prospecting tool, then read the stored contact and source rows.

**Acceptance Scenarios**:

1. **Given** a contact proposal from email, calendar, conversation or manual entry, **When** it is stored, **Then** the contact source (and a contact it creates) is `prompt_supplied`.
2. **Given** a contact added by prospecting web research, **When** it is stored, **Then** the source is `live_search`.
3. **Given** a co-occurrence hypothesis built from email or calendar evidence, **When** its evidence is written, **Then** the evidence origin is `prompt_supplied`.

### Edge Cases

- **A fact written by a dream run whose run row was deleted.** The dream marker on the fact stands on its own; decay does not join to the run table.
- **A dream insight that says the same thing as a user fact.** Consolidation does not merge them; the insight keeps its own decay and expiry, and the user fact keeps its provenance.
- **Two near-duplicate facts with different provenance.** Consolidation does not merge them, because no single label is true for the merged text.
- **Facts decay already damaged.** They keep their lowered confidence and flags (Clarification Q2); the repair counts them. Facts consolidation already deleted are gone.
- **A resolve that matches no live loop.** Nothing changes and no error is logged (as today).
- **Two resolves of the same loop at once.** One closes it; the other sees a closed loop and changes nothing.
- **A resolve that matches a loop with no evidence passed** (e.g., an inflow that has none). The loop closes; nothing is linked.
- **A loop created through the contribution seam with a claim kind that disagrees with its starting state.** Refused before the row is written (the declared kind must match the state table).
- **Seed and eval fixtures that insert loops or facts directly.** They stop naming `open_loops.claim_kind` and use the corrected provenance.

## Requirements *(mandatory)*

### Functional Requirements

**Provenance (B7, `user-statement-provenance.md`)**

- **FR-001**: Facts perception reads from the user or the user's own sources MUST be stored `prompt_supplied`: the conversation fact path in `write_memory`, the ingestion sink, and the inbound-message extractor.
- **FR-002**: `synthesized` MUST be written to `memory_facts` only by reflection (the dream promoter). `live_search` MUST mean a web search only.
- **FR-002a**: Consolidation's merge MUST NOT write `synthesized`. A merged fact MUST carry the provenance and claim kind its two inputs share. Consolidation MUST merge two facts only when neither has a dream run and both have the same provenance and claim kind; otherwise it MUST leave both facts unchanged.
- **FR-003**: Dream decay and dream expiry MUST select only facts the dream wrote, in addition to their current conditions, so a wrong provenance cannot make them touch a perception fact. The marker that identifies "the dream wrote this" is `dream_run_id IS NOT NULL`; no column is added.
- **FR-004**: The dream promoter MUST be able to store a synthesized insight: its insert stops naming `creation_method`, which `memory_facts` does not have. Decay and expiry MUST run on a night with a promotion.
- **FR-005**: A one-time migration on the `zm` chain MUST re-stamp every `memory_facts` row that is `synthesized` and was not written by the dream to `prompt_supplied`, and set its claim kind to `fact`. Dream-written facts and facts with any other provenance MUST be untouched. Running the repair twice MUST change nothing the second time.
- **FR-006**: The repair MUST expose its SQL as a module constant so a test-pg test runs it on seeded rows (the `zm025` pattern), and it MUST log the number of rows it re-stamped and how many of them carry the decay signature.
- **FR-007**: The repair MUST NOT change confidence, `reviewed` or `contradicted`. It MUST count the re-stamped facts that carry the decay signature (contradicted, confidence below 0.25, uncorroborated) and include that count in its log line.
- **FR-008**: A stored contact source's provenance MUST follow from its source type: `manual`, `conversation`, `email`, `calendar` → `prompt_supplied`; `research` → `live_search`. This holds on every write path (the consolidator, the graph memory hook, prospecting). A contact a source creates takes that source's provenance.
- **FR-008a**: Co-occurrence hypothesis evidence from email or calendar MUST carry origin `prompt_supplied`, not `live_search`.
- **FR-008b**: A one-time migration on the `zc` chain (owned by ze-personal) MUST re-stamp existing `contact_sources` rows from their source type and each `contacts` row from its earliest source. A contact with no source keeps its value. It MUST be idempotent and expose its SQL for a test-pg test.

**Loop claim kind (B12, `loop-claim-kind-from-state.md`)**

- **FR-009**: A loop's claim kind MUST be derived from its state on every read: `suspected` → suspicion; `active`, `drifting`, `closed` → priority; `dropped` → none. It MUST NOT be stored.
- **FR-010**: The `open_loops.claim_kind` column MUST be dropped by a `zw` migration (pre-v1 hard cut, no dual read).
- **FR-011**: Every reader MUST get the derived kind: `PriorityItem.claim_kind`, the composed loop posture, the loops REST response, the loop screen resolver, and the contribution built for a new loop. A dropped loop MUST NOT appear with a claim kind on any surface.
- **FR-012**: Creating a loop MUST still submit a contribution that declares a claim kind, and that kind MUST equal the derived kind of the starting state, so the contribution seam is unchanged.
- **FR-013**: The REST field `claim_kind` on loop responses MUST keep its name and its values (`suspicion`, `priority`) and becomes nullable: it is `null` for a dropped loop, which `GET /api/v0/loops?state=dropped` can return. The generated `@myguyze/ze-client` types are regenerated, and the web readers (`concerns.ts`, `LoopsRail.tsx`, `DoingGoalPage.tsx`) still type-check and show no posture for a null kind.

**Executive licence (B8, `executive-licence.md`)**

- **FR-014**: The Executive licence MUST be exactly {priority, suspicion}. Perception's stays {fact, feedback_record}. Other licences are unchanged.
- **FR-015**: `contribution-seam.md` MUST attribute candidate loops to Executive (the ADR's amendment). Its licensing row already does (line 99, 2026-10-22); this phase checks that no other text says Perception.

**Suspected loop resolution (B3, `suspected-loop-resolution.md`)**

- **FR-016**: A resolve event MUST move a matching `suspected`, `active` or `drifting` loop to `closed`, stamp `closed_at`, and link the resolving evidence to the loop, for conversation, email, calendar and ingestion.
- **FR-017**: The `suspected → closed` edge MUST be available to the resolve event only. The generic transition used by the REST close route, the `close_loop` tool, the confirm route, decay and the drift sweep MUST keep refusing it.
- **FR-018**: A resolve MUST NOT write a dismissed-evidence fingerprint.
- **FR-019**: A resolve that fails for a reason other than "no matching loop" MUST still surface as `loop_extraction_failed`; a resolve of a suspected loop MUST no longer produce that log line.

**Testing and docs**

- **FR-020**: Each fix MUST begin with a test that fails on today's code, through the real interface (graph node, sink, inflow, store, seam), against test-pg wherever the behaviour is SQL. Tests that mock the store MUST NOT be the only proof of a fix.
- **FR-021**: Public docs and indexes MUST describe the new behaviour: `AGENTS.md` (phase row; migration ownership rows for `zm`, `zw` and `zc`), the `specs/README.md` status cell, `docs/dreaming.md` (decay and expiry apply to dream insights only), `docs/architecture.md` (post-turn extraction stores `prompt_supplied` facts; expiry wording), `docs/memory.md` (fact provenance), `docs/goals.md:162` (already stale: promotion is `prompt_supplied`), `docs/features.md` (loop state machine, if it shows resolve edges), and the ze-worldstate and ze-memory READMEs. The docs task ends with a coverage check against `git diff main...HEAD`.

### Key Entities

- **Fact** (`memory_facts`): a stored belief with provenance, claim kind, confidence, `reviewed`, `contradicted`, `corroborated`, `valid_until` and, for dream insights, `dream_run_id`.
- **Dream insight**: a fact the dream promoter writes (`synthesized`, claim kind inference, `agent=dream`, with `dream_run_id` and `valid_until`). The only fact that decays and expires.
- **Open loop** (`open_loops`): a concern Executive tracks; its claim kind is a function of its state.
- **Resolving evidence**: the episode, email, calendar or ingestion reference whose text said the concern is done; linked to the loop on resolve.
- **Licence table**: the closed map from source function to the claim kinds it may submit.
- **Contact source** (`contact_sources`): one sighting of a person, with source type, weight and provenance.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A fact the user states in conversation keeps the confidence, `reviewed` and `contradicted` it was stored with after 10 runs of the dream integration step on a fact aged 60 days (0 changes).
- **SC-002**: Dream insights keep today's behaviour: confidence falls by exactly 0.03 per run after 30 days, and every insight past `valid_until` is contradicted.
- **SC-003**: After the repair, 0 facts outside dream insights are labelled `synthesized`, no writer other than the dream promoter creates one afterwards (consolidation included), the count of decay-damaged facts is reported, and a second run reports 0 rows changed.
- **SC-004**: 100% of confirmed or promoted loops read `priority` on every surface, and 0 dropped loops are shown with a claim kind.
- **SC-005**: A resolve of a suspected loop closes it in 100% of test cases across the four inflows, with its evidence linked, and produces 0 `loop_extraction_failed` lines.
- **SC-006**: 0 contributions with claim kind fact, inference or identity are accepted from Executive.
- **SC-007**: Every fix has at least one test that failed before the change and passes after it; every SQL-backed fix has at least one test-pg test.

## Assumptions

- **ADR decisions are settled** (D1–D4). The open questions are implementation gaps the ADRs did not foresee, not re-openings.
- **Migration chains**: fact repair on `zm` (ze-memory owns `memory_facts`; next is `zm026`); dropping `open_loops.claim_kind` on `zw` (next is `zw006`); contact re-stamp, if in scope, on the shared `zc` chain from ze-personal (next free number coordinated with floor 198).
- **Floor 198** also edits `ze_core/orchestration/nodes/memory.py` (the compaction lines). This phase owns only the provenance at line 217.
- **Phase 203** later moves the resolve event and the derived claim kind into its lifecycle module and does not decide them again. This phase keeps the change small: one resolve method on the loop store, one derivation function, no lifecycle refactor.
- **Loop provenance on contributions** (`ze_worldstate/contribution.py`, conversation and ingestion loops → `synthesized`) is out of scope: a loop is an Executive judgment, not a perception fact.
- **Social cognition identity edges** (`graph/memory_hooks.py:166`) and **procedure candidates** keep `synthesized`: they are interpretations, not perception.
- **The resolving evidence** is what the inflow already has: the turn's episode for conversation, the message reference for email, the ingestion id for ingestion; calendar has none today, so nothing is linked for it.
- **Pre-v1 hard cut** (constitution Principle VIII): no compatibility read of the dropped column, no dual-write of provenance.
