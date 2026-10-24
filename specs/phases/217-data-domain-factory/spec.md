# Feature Specification: Data Domain Factory

**Feature Branch**: `217-data-domain-factory`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 211 (Personal unbundling). 211 stops ze-personal from declaring tables it does not own and moves the contacts and channel tables to their new owners, so each owner can declare its own tables here. It also needs 210 (Plugin seam narrowing), which settles the shape of the plugin hooks, including `data_domains`.

**Input**: Architecture review 2026-10-22, candidate C17 ("One table-domain factory for data portability") and bug B13 ("Goals and workflows may be exported twice: by ze-automation and again by ze-personal"). Approved by the user ("go ahead with all of it").

## Context

Governance › Data lets the user see what Ze holds, export it as a ZIP, import that ZIP into an empty instance, and delete everything. The service behind it (`DataPortabilityService`, `core/kernel/ze-data/ze_data/portability/service.py`) runs over a flat list of `DataDomain` records (`ze_data/domain.py:7-23`). Each record carries hand-written `export`, `delete`, `importer`, `count` and `size_bytes` closures and a hand-picked `delete_order`. ze-api concatenates the lists at `apps/ze-api/ze_api/wiring/container.py:615-622`.

Verified against the code on 2026-10-22:

**The closure factory is hand-written nine times, not six.** All copies run the same SQL (`SELECT * FROM t`, `DELETE FROM t`, `SELECT COUNT(*)`, `pg_total_relation_size`) and import through the shared `bulk_insert` (`ze_data/portability/assembler.py:78-88`). They come in five shapes:

| Site | Shape |
|---|---|
| `ze_core/bootstrap.py:186` (`engine_data_domains`) | Nested helpers that capture the outer pool and ignore the pool argument; `onboarding` exports one table but deletes three |
| `ze_automation/bootstrap.py:84` | Same shape |
| `ze_worldstate/bootstrap.py:141` | Same helpers, `DataDomain(...)` inline |
| `ze_personal/plugin.py:127-212` | Helpers that use the pool argument, explicit order |
| `ze_calendar/plugin.py:57-103`, `ze_prospecting/plugin.py:51-95` | Async helpers bound with `lambda p, t=tbl:` |
| `ze_finance/plugin.py:159-252` | Written out per table, and **no importer**: a restore silently drops all finance data |
| `ze_memory/feedback_records/data_domain.py:11`, `ze_proactive/data_domain.py:11` | One table, module-level closures |

**B13 is real, but narrower than reported.** Two tables are declared twice:

- `goals`, as `automation.goals` (`ze_automation/bootstrap.py:137`, order 10) and `goals.goals` (`ze_personal/plugin.py:210`, order 30);
- `workflows`, as `automation.workflows` (`:138`, order 10) and `workflow.workflows` (`:211`, order 30).

The audit said memory tables are exported twice too. They are not: ze-personal is the only package that declares the `memory_*` tables. That is still wrong, since ze-memory owns them, but it is not a duplicate. ze-personal also declares `goal_*`, `workflow_executions` and `persona_state`, which it does not own.

What the duplicates do:

- **Double counting.** `GET /api/v0/data/domains` sums every domain's count and size (`apps/ze-api/ze_api/api/v0/data/router.py:52-53`), so `total_records` and `total_size_bytes` count goals and workflows twice. The web page shows one row per domain, so the user sees "Automation goals" and "Goals" with the same number (`apps/ze-web/src/widgets/data/lib/domain-labels.ts`).
- **Double import.** The restore inserts goals at order 30 and again at order 10. `ON CONFLICT DO NOTHING` (`assembler.py:85`) makes the second insert a no-op, but `bulk_insert` returns `len(rows)`, not the rows inserted, so `rows_imported` overstates the restore.
- **A delete that can fail.** The duplicate pulls `goals` and `workflows` down to delete order 10, the same group as `open_loops`. Each order group is deleted concurrently (`service.py:165-173`). `open_loops.goal_id` references `goals(id)` with no `ON DELETE` clause (`ze_worldstate/migrations/versions/zw001_open_loops.py:29`), so "Delete all data" can fail with a foreign-key error, depending on timing.
- **Nothing catches it.** There is no check for a repeated domain name or table. A repeated name would silently overwrite an export entry (`service.py:85-87`, the ZIP entry `{name}.json`).

**Coverage is worse than duplication.** 45 live tables are declared by no domain. Export leaves them out, and "Delete all data" leaves them in place unless a foreign key cascades. By owner:

| Owner | Tables no domain declares |
|---|---|
| ze-memory | `action_records`, `memory_signals`, `memory_session_summaries`, `memory_episode_metadata`, `memory_retrieval_cache`, `memory_dream_runs`, `memory_dream_artifacts`, `memory_dream_journal`, and nine `procedure_*` tables (`candidates`, `admissions`, `identities`, `provisionals`, `lifecycle_events`, `invocations`, `feedback`, `activation_feedback`, `action_links`) |
| ze-automation | `held_writes`, `workflow_revisions`, `goal_learning_promotions`, `goal_learning_relationships`, `goal_learning_reviews` |
| ze-personal (contacts and channels, moving in 211) | `contacts_episode_watermark`, `user_channels`, `user_channel_watermarks`, `thread_channel_map` |
| ze-proactive | `notifications`, `proactive_job_runs` |
| ze-skills | `skills`, `skill_reference_files`, `skill_reviews`, `skill_scripts` |
| ze-workspace | `workspace_state`, `workspace_runs` |
| ze-onboarding | `onboarding_steps`, `onboarding_seeds` (deleted, not exported, by ze-core's `onboarding` domain) |
| Others | `correlation_hypothesis`, `open_loop_sources`, `ingested_content`, `contribution_collisions`, `priority_overrides`, `messenger_outbound_sends`, `news_articles`, `finance_recurring_staleness` (deleted by `finance.recurring`, not exported), `checkpoint_migrations` |

Several tables are also declared by a package that does not own them: ze-core declares `push_log` (ze-proactive) and `onboarding_sessions` (ze-onboarding); ze-personal declares the memory, goal and workflow tables above.

**No tests.** `core/kernel/ze-data` has no `tests/` directory. Nothing tests the service, the assembler, `bulk_insert`, duplicate tables or an export, delete and import round trip. The existing tests check table names in single packages (`plugins/ze-personal/tests/test_data_domains.py`, `ze-memory/tests/feedback_records/test_data_domain.py`, `ze-proactive/tests/test_data_domain.py`) or read source text (`apps/ze-api/tests/test_message_export_columns.py`).

**Blast radius.** `graphify affected DataDomain --depth 2` returns 152 nodes: ze-api 23, core contracts 13, ze-personal 10, ze-core 10, cognition 10, automation 8, finance 7, calendar 7, news 4, messenger 4, prospecting 3, priority 2, ze-sdk 1, and 40 test nodes. `graphify affected DataPortabilityService --depth 2` returns 42, all in the ze-api data router and its tests.

**REST and SDK surface** (unchanged by this phase): `GET /api/v0/data/domains` (`listDataDomains`), `GET /api/v0/data/export` (`exportData`, `downloadExport`), `POST /api/v0/data/import` (`importData`, `importArchive`), `POST /api/v0/data/delete-intent` (`createDeleteIntent`) and `DELETE /api/v0/data` (`deleteData`).

**Doctrine function.** Governance: the user can see, take and erase everything Ze holds.

## Clarifications

### Session 2026-10-22

- Q: How much coverage: every table, or only the duplicates and the factory? → A: Every table is declared once or excluded with a reason, and a test enforces it, so "Delete all data" deletes everything.
- Q: How is Governance › Data grouped? → A: One row per area (Goals, Workflows, Facts, Contacts, …), about 25 rows. Each row shows the count of the area's main table ("3 goals"). The archive keeps one file per table.
- Q: What if one domain fails during export? → A: The whole export fails and names the domain, so the user never keeps a partial backup that looks complete.

## User Scenarios & Testing *(mandatory)*

The users of this phase are Ze's user, who expects Governance › Data to be complete and true, and the developer who adds a table and must make it portable in one line.

### User Story 1 - "Delete all data" deletes all data (Priority: P1)

The user deletes everything from Governance › Data. Afterwards no table that holds the user's data has a row left, and the delete never fails part-way because of the order it ran in.

**Why this priority**: It is a privacy promise the product makes today and does not keep. Action records, notifications, connected channels, skills and dream output survive a delete.

**Independent Test**: Seed every table with at least one row, run the delete, and check that every declared table is empty and that the delete ran without error.

**Acceptance Scenarios**:

1. **Given** a database with rows in every table, including an open loop that references a goal, **When** the user deletes all data, **Then** the delete succeeds and every table that holds user data is empty.
2. **Given** a table that a migration adds after this phase, **When** the test suite runs and the table is in no domain and not on the exclusion list, **Then** a test fails and names the table.

---

### User Story 2 - Export and restore round-trip (Priority: P1)

The user exports their data, deletes it, and imports the ZIP into the same instance. Every row comes back, and the import reports the true number of rows it restored.

**Why this priority**: Today a restore loses all finance data (no importer) and every table outside a domain, and it reports goals and workflows twice.

**Independent Test**: Seed every exportable table, export, delete, import, and compare each table's rows with the seed.

**Acceptance Scenarios**:

1. **Given** finance accounts and transactions, **When** the user exports, deletes and imports, **Then** the finance rows are back.
2. **Given** 3 goals, **When** the user imports an export of them, **Then** the import result says 3 goal rows, not 6.
3. **Given** a table that is derived or a cache, **When** the user exports, **Then** it is not in the archive, and it is still emptied by "Delete all data".

---

### User Story 3 - Governance › Data shows each table once (Priority: P2)

The list on Governance › Data shows one row per area of what Ze holds (about 25 rows), each with the count of its main records, and the totals match the rows in the database.

**Why this priority**: The user sees "Automation goals" and "Goals" with the same number today, and the API totals are inflated.

**Independent Test**: Seed known row counts and compare the API's per-domain counts and totals with them.

**Acceptance Scenarios**:

1. **Given** 4 goals with 9 milestones and 2 workflows, **When** the user opens Governance › Data, **Then** Goals appears once with 4 and Workflows once with 2.
2. **Given** the domain list, **When** `total_records` is read, **Then** it equals the sum of rows over the declared tables, each table counted once.

---

### User Story 4 - An owner declares its tables once (Priority: P2)

A developer who adds a table to a package adds it to that package's one table declaration. They write no SQL and no closures, and they pick no delete order.

**Why this priority**: Nine hand-written copies drifted into five shapes, one with no importer. The factory removes that whole class of mistake.

**Independent Test**: Every package that owns tables declares them through the factory, and a test fails when two owners declare one table or two domains share a name.

**Acceptance Scenarios**:

1. **Given** two packages that both declare `goals`, **When** the container starts, **Then** startup fails with an error that names the table and both packages.
2. **Given** two domains with the same name, **When** the container starts, **Then** startup fails with an error that names the domain.
3. **Given** the code base, **When** it is searched for hand-written `DataDomain(` construction outside ze-data, **Then** nothing is found.

### Edge Cases

- **A table with a foreign key to another owner's table** (`open_loops.goal_id` → `goals`). The delete and the import follow the foreign keys between declared tables, whichever packages own them. No owner picks a number.
- **A table whose migration and store live in different packages** (`goals` is created by ze-core's `003` migration but written by ze-automation's `PostgresGoalStore`; `persona_state` is created by ze-core but written by ze-personal). The package that owns the store that writes the table declares it.
- **A domain that spans several tables** (`onboarding` today exports one table and deletes three; `finance.recurring` also deletes `finance_recurring_staleness`). Each table is declared by itself, so export and delete cover the same tables.
- **A plugin is disabled.** Its tables still exist in the database, because migrations always run. Its declarations must still be collected, so a delete empties them. The plan says how a disabled plugin's declarations are collected.
- **LangGraph checkpoint tables** are opaque blobs. They are deleted but not exported or imported, as today. `checkpoint_migrations` is LangGraph's own bookkeeping and is excluded.
- **An archive made before this phase.** Pre-v1, an old archive is refused because its schema revisions differ, as today (`service.py:118-123`). No compatibility reader is added (Principle VIII).
- **An export where one domain fails.** Today it is written as `[]` with a log line (`service.py:79-88`), and the user gets an incomplete archive with no warning. The export MUST fail instead, so the user never keeps a partial backup that looks complete.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: ze-data MUST offer one table-domain factory. An owner declares a table by its name, the domain (area) it belongs to, whether it is that domain's main table, and whether it is user data (exported, imported, deleted) or derived (deleted only). Each domain MUST have exactly one main table. The factory builds export, import, delete, count and size from that declaration.
- **FR-002**: Every package that owns tables MUST declare them through the factory, exactly once. The nine hand-written sites MUST be deleted, and no code outside ze-data MAY construct `DataDomain` by hand.
- **FR-003**: The package that owns the store writing a table MUST declare it. ze-personal MUST NOT declare the memory, goal, workflow or persona tables it declares today unless it owns their store. After 211 that means the memory tables move to ze-memory, the goal and workflow tables to ze-automation, `push_log` to ze-proactive and `onboarding_*` to ze-onboarding.
- **FR-004**: Startup MUST fail when two declarations name the same table or two domains share a name. The error MUST name the table or domain and both declaring packages.
- **FR-005**: Delete and import order MUST follow the foreign keys between declared tables. No declaration MAY carry a hand-picked order. "Delete all data" MUST NOT fail because two tables were deleted in the wrong order or at the same time.
- **FR-006**: Every table in the migrated schema MUST be declared by exactly one owner or listed on one explicit exclusion list in ze-api, each entry with a reason (for example `alembic_version`, `checkpoint_migrations`). A test MUST compare the schema with the declarations and the exclusion list, and fail on any table in neither.
- **FR-007**: Import MUST report the number of rows it actually inserted per domain.
- **FR-008**: Export MUST fail, and say which domain failed, when any domain's export fails. It MUST NOT write an empty file for a failed domain.
- **FR-009**: Every user-data table MUST be importable. A table that cannot be restored MUST be declared as derived, with the reason in its declaration.
- **FR-010**: `GET /api/v0/data/domains` MUST return one entry per domain (area), whose count is the rows in that domain's main table. Its totals MUST equal the sum over all declared tables, each counted once. The archive MUST hold one file per table. The web labels in `domain-labels.ts` MUST cover every domain name, with no label for a removed name.
- **FR-011**: ze-data MUST have its own tests: the factory, the duplicate checks, foreign-key ordering, row counts on import, and an export, delete and import round trip on real Postgres (`@pytest.mark.pg`).
- **FR-012**: Pre-v1 hard cut (Principle VIII): domain names, archive file names and the `DataDomain` shape may change, with no aliases and no reader for old archives.

### Key Entities

- **Table declaration**: one owner's statement that it owns a table, the domain the table belongs to, and whether the table is user data or derived.
- **Data domain**: one area of what Ze holds (Goals, Facts, Contacts, …): a named group of tables with one main table. It is one row on Governance › Data, counted by its main table. Each of its tables is one file in the archive.
- **Exclusion list**: the tables Ze knows about and deliberately leaves out of portability, each with a reason.
- **Owner**: the package whose store writes a table.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After "Delete all data" on a database seeded in every table, 0 user-data rows remain, in 10 runs out of 10.
- **SC-002**: An export, delete and import round trip restores 100% of the rows in every user-data table, and the reported row counts equal the rows restored.
- **SC-003**: Every table in the schema is declared once or excluded with a reason. The coverage test proves it, and fails when a new table is added without either.
- **SC-004**: Governance › Data shows about 25 rows, one per area, each counting its main table. The API totals equal the seeded row count.
- **SC-005**: Adding a portable table takes one declaration line in its owner and no SQL.
- **SC-006**: `make test-py`, `make test-pg` and `make test-web` pass.

## Assumptions

- Phase 211 has moved contacts and the channel stores to their owners and stopped ze-personal declaring tables it does not own. Phase 210 has settled the plugin hook shape.
- The archive format stays a ZIP with a manifest and one JSON file per domain.
- The schema-revision check on import stays as it is.
- The REST routes, their response shapes and the ze-client functions keep their names. Only domain names and counts change.
- Derived tables are those Ze can rebuild or that only cache other data, such as `memory_retrieval_cache`, LangGraph checkpoints and `proactive_job_runs`. The plan lists each one.
