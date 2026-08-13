---

description: "Task list for Agent Skills (phase 114)"
---

# Tasks: Agent Skills

**Input**: Design documents from `/specs/phases/114-agent-skills/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/skills-api.md, quickstart.md

**Tests**: Included per `CLAUDE.md`'s Test Discipline convention and plan.md §Testing (pytest for
`ze-skills`/route tests, vitest for the management widget) — not a strict TDD gate, but every
implementation task that adds testable logic has a paired test task in the same story phase.

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P1/P2/P3) so each story
is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 (import + approve), US2 (visible usage), US3 (management view), US4 (recheck)
- Every task names an exact file path

## Path Conventions

Existing monorepo layout (see root `CLAUDE.md`) — `core/ze-skills/` (new package),
`core/ze-core/`, `core/ze-agents/`, `core/ze-plugin/`, `apps/ze-api/`, `apps/ze-web/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold the new `ze-skills` package so later phases have somewhere to add code.

- [X] T001 Create `core/ze-skills/pyproject.toml` (deps: `ze-agents`, `ze-proactive`,
      `ze-logging`, `ze-data`, `httpx`, `asyncpg==0.31.0`, dev group mirrors
      `core/ze-worldstate/pyproject.toml`; `[tool.hatch.build.targets.wheel] packages =
      ["ze_skills"]`; `testpaths = ["tests"]`, `asyncio_mode = "auto"`)
- [X] T002 [P] Create `core/ze-skills/ze_skills/__init__.py` (empty package marker)
- [X] T003 [P] Create `core/ze-skills/tests/__init__.py` and `core/ze-skills/tests/conftest.py`
      (shared fixtures: mock asyncpg pool, mock `httpx.AsyncClient`, mock embedder — mirrors
      `core/ze-worldstate/tests/conftest.py`)
- [X] T004 Add `ze-skills` to `apps/ze-api/pyproject.toml` dependencies and
      `[tool.uv.sources]` (`ze-skills = { workspace = true }`)
- [X] T005 Add a `test-skills` target to the root `Makefile`, mirroring `test-worldstate`
      (`.PHONY` line + `cd core/ze-skills && uv run pytest`), and list it in `make help`'s
      target list

**Checkpoint**: `uv sync` resolves the new package; `make test-skills` runs (0 tests yet); no
domain code yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Domain types, errors, schema, and the store — every user story depends on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 [P] Define `SkillStatus`, `SkillSource`, `SkillTrigger` `StrEnum`s and `Skill`,
      `ReferenceFile`, `SkillReview`, `SkillMatch` dataclasses in
      `core/ze-skills/ze_skills/types.py` (per data-model.md; `Skill.slug` derivation helper,
      `content_hash` computed from `(name, description, instructions, allowed_tools)`;
      `SkillMatch` is the intermediate `{skill, trigger, similarity}` shape produced by the
      matcher and consumed by both `AgentContext` population and `SkillUsageTrace`
      construction — see data-model.md's `SkillMatch` section)
- [X] T007 [P] Define `SkillParseError`, `SkillNotFoundError`, `InvalidSkillTransitionError` in
      `core/ze-skills/ze_skills/errors.py` (subclass `ZeError` per `ze_agents/errors.py`
      hierarchy)
- [X] T008 Add `SkillUsageTrace` dataclass and `MessageTrace.skills_used: list[SkillUsageTrace]
      = field(default_factory=list)` in
      `core/ze-core/ze_core/conversation/messages/types.py` (per data-model.md — existing
      fields unchanged)
- [X] T009 Create `core/ze-skills/ze_skills/migrations/env.py` (Alembic env boilerplate,
      mirrors `core/ze-worldstate/ze_worldstate/migrations/env.py`)
- [X] T010 Create `core/ze-skills/ze_skills/migrations/versions/zsk001_skills.py` — raw-SQL
      migration creating `skills`, `skill_reference_files`, `skill_reviews` tables per
      data-model.md (unique index on `(slug, source)` for `skills`; `ON DELETE CASCADE` FKs
      from `skill_reference_files.skill_id` and `skill_reviews.skill_id`)
- [X] T011 Register `_ZE_SKILLS_VERSIONS` constant pointing at
      `core/ze-skills/ze_skills/migrations/versions` in `apps/ze-api/ze_api/migrate.py`
      (alongside `_ZE_WORLDSTATE_VERSIONS`)
- [X] T012 Implement `SkillStore` protocol and `PostgresSkillStore` in
      `core/ze-skills/ze_skills/store.py` — CRUD + status-filtered list + conditional
      transition updates (`WHERE status = $expected`, mirrors
      `ze_automation.goals.suggestion_store.GoalSuggestionStore`) + reference-file read/write,
      including a single-file lookup by `(skill_id, filename)` for the reference-file content
      route
- [X] T013 [P] Unit tests for `PostgresSkillStore` in
      `core/ze-skills/tests/test_store.py` (mock asyncpg pool; covers create, get, list with
      filters, conditional transitions succeeding/failing on stale status, single reference
      file lookup)
- [X] T014 [P] Unit tests for `types.py` slug derivation and `content_hash`
      stability/sensitivity in `core/ze-skills/tests/test_types.py`

**Checkpoint**: Schema, types, and store exist and are tested — user story implementation can
now begin.

---

## Phase 3: User Story 1 - Import a skill from a URL and approve it (Priority: P1) 🎯 MVP

**Goal**: A user can submit a `SKILL.md` URL, see the fully parsed content for review, and
approve or reject it before it ever affects a conversation.

**Independent Test**: Submit a URL to a valid `SKILL.md`, confirm parsed content is returned
unactivated, approve it, confirm it shows `status: active` via `GET /api/v0/skills`.

### Tests for User Story 1

- [X] T015 [P] [US1] Unit tests for `parse_skill_md()` in
      `core/ze-skills/tests/test_parser.py` — valid frontmatter, missing name/description
      (FR-018 rejection), malformed YAML, `allowed-tools` list parsing, bundled-script
      reference detection (FR-009)
- [X] T016 [P] [US1] Unit tests for `fetch_skill_source()` in
      `core/ze-skills/tests/test_importer.py` — direct `SKILL.md` URL, zip archive with
      supporting reference files, unreachable URL, mocked `httpx.AsyncClient`
- [X] T017 [P] [US1] Unit tests for approve/reject transitions in
      `core/ze-skills/tests/test_review.py` — pending→active, pending→rejected, 409-equivalent
      error on non-pending source status (`InvalidSkillTransitionError`)
- [X] T018 [US1] REST route tests for import/approve/reject in
      `apps/ze-api/tests/api/routes/test_skills.py` — `POST /import` success (201) and parse
      failure (422, no row created per FR-003), `POST /{id}/approve`, `POST /{id}/reject`,
      `GET /{id}` full detail, `GET /skills` filtered list, and
      `GET /{id}/reference-files/{filename}` (200 with content, 404 for unknown filename)

### Implementation for User Story 1

- [X] T019 [US1] Implement `parse_skill_md()` in `core/ze-skills/ze_skills/parser.py` —
      YAML frontmatter (name, description, `allowed-tools`) + Markdown body parsing per the
      open Agent Skills format; raises `SkillParseError` on missing/empty name or description
      (FR-018); detects references to bundled executable scripts and sets
      `has_unsupported_scripts` (FR-009) without blocking the parse
- [X] T020 [US1] Implement `fetch_skill_source()` in `core/ze-skills/ze_skills/importer.py` —
      `httpx.AsyncClient` fetch of a direct `SKILL.md` URL or a zip archive (stdlib `zipfile`),
      extracts `SKILL.md` + non-script reference files, calls `parse_skill_md()`, raises
      `SkillParseError` on unreachable URL (FR-003)
- [X] T021 [US1] Implement `approve_skill`, `reject_skill` in
      `core/ze-skills/ze_skills/review.py` — conditional `pending_review → active` /
      `pending_review → rejected` transitions via `SkillStore`, writes a `SkillReview` row
      with the content snapshot (FR-006, FR-016)
- [X] T022 [US1] Implement `import_skill()` orchestration in
      `core/ze-skills/ze_skills/rest.py` — calls `fetch_skill_source()`, persists a new
      `Skill` row (`status=pending_review`, `source=imported`) plus its `ReferenceFile` rows
      via `SkillStore`, never activates (FR-004); implement `get_skill()`, `list_skills()`,
      `get_reference_file()`, `approve()`, `reject()` thin wrappers returning plain dicts
- [X] T023 [US1] Add `SkillResponse`, `SkillListResponse`, `SkillDetailResponse`,
      `SkillImportRequest`, `SkillReferenceFileResponse` Pydantic schemas to
      `apps/ze-api/ze_api/api/schemas.py` per contracts/skills-api.md (including
      `previous_version` optional field on detail response)
- [X] T024 [US1] Implement `apps/ze-api/ze_api/api/routes/skills.py` —
      `GET /api/v0/skills` (status/source filters), `GET /api/v0/skills/{id}`,
      `GET /api/v0/skills/{id}/reference-files/{filename}`, `POST /api/v0/skills/import`,
      `POST /api/v0/skills/{id}/approve`, `POST /api/v0/skills/{id}/reject`;
      `require_api_key` dependency; `response_model`, `summary`, `description` on every route;
      `404`/`409`/`422` mapped from
      `SkillNotFoundError`/`InvalidSkillTransitionError`/`SkillParseError`
- [X] T025 [US1] Create `build_skills_stack(shared, settings)` in
      `core/ze-skills/ze_skills/bootstrap.py` — constructs `PostgresSkillStore` from the
      shared asyncpg pool
- [X] T026 [US1] Wire `build_skills_stack` into `apps/ze-api/ze_api/container.py` and
      register `skills.router` in `apps/ze-api/ze_api/api/app.py`
      (`app.include_router(skills.router, prefix="/api/v0")`)

**Checkpoint**: User Story 1 fully functional — quickstart.md Scenarios 1–3 pass end-to-end.

---

## Phase 4: User Story 2 - See when Ze uses a skill in conversation (Priority: P1)

**Goal**: Active skills are matched to a turn (automatically or via `/skill-name`), their
instructions shape the response, tool access is only ever narrowed, and usage is visibly
attributed on the message trace.

**Independent Test**: Approve a skill with a distinctive checkable instruction, send a matching
message, confirm both the behavior and a `skills_used` trace entry appear.

### Tests for User Story 2

- [X] T027 [P] [US2] Unit tests for `SkillMatcher` in
      `core/ze-skills/tests/test_matching.py` — embedding-similarity match above/below
      `match_threshold`, `/skill-name` explicit-invocation parsing and precedence, combined
      automatic + explicit matches in one turn (each producing a `SkillMatch`), mocked embedder
- [X] T028 [P] [US2] Unit tests for tool-narrowing intersection logic in
      `core/ze-agents/tests/test_base_agent.py` (extend existing suite) — agent `tools`
      intersected with a skill's `allowed_tools` (never unioned, FR-008), multiple matched
      skills' restrictions intersected together, restriction naming a tool the agent lacks
      has no effect (spec Edge Cases)
- [X] T029 [P] [US2] Unit test for `match_skills` orchestration node in
      `core/ze-core/tests/orchestration/test_skills_node.py` — populates
      `AgentContext.active_skills`/`skill_tool_names`, no-op when no skills active
- [X] T030 [US2] Integration-style trace test extending
      `apps/ze-api/tests/api/routes/test_messages.py` (or equivalent existing trace test file)
      — `skills_used` present on `GET /api/v0/messages/{id}/trace` and empty array when no
      skill matched

### Implementation for User Story 2

- [X] T031 [US2] Implement `SkillMatcher` in `core/ze-skills/ze_skills/matching.py` —
      embeds each active skill's `name + description` once (cache invalidated on
      approve/disable/enable/content-change), cosine-similarity against the turn's routing
      embedding via the injected embedder (`EmbeddingRouter` pattern), applies
      `skills.match_threshold`, producing a `SkillMatch` with `trigger="automatic"`;
      regex-parses `/skill-name` tokens from the raw message and resolves against active
      skills' slugs, producing a `SkillMatch` with `trigger="explicit"`; combines both sets
      for the turn (FR-019a, FR-019b)
- [X] T032 [US2] Add `active_skills: list[Skill]` and `skill_tool_names: list[str] | None`
      fields to `AgentContext` in `core/ze-agents/ze_agents/types.py`
- [X] T033 [US2] Create `match_skills(state, config)` node in
      `core/ze-core/ze_core/orchestration/nodes/skills.py` — reads `SkillMatcher` from
      `config["configurable"]["skill_matcher"]` (mirrors `surface_loops`/`loop_surfacer`),
      populates `AgentContext.active_skills`/`skill_tool_names` from the turn's `SkillMatch`
      list and stores that list on state for `record_trace` to consume; wire
      `add_node("match_skills", ...)` after `embed_route` in
      `core/ze-core/ze_core/orchestration/graph.py`
- [X] T034 [US2] Update `record_trace` in
      `core/ze-core/ze_core/orchestration/nodes/trace.py` to populate
      `MessageTrace.skills_used` from the turn's `SkillMatch` list (name, source, trigger,
      similarity)
- [X] T035 [US2] In `core/ze-agents/ze_agents/base_agent.py`: `_build_system_prompt` prepends
      each active skill's instructions (and referenced reference-file content per FR-022) to
      the system prompt; `agentic_loop`'s tool-name resolution intersects
      `AgentContext.skill_tool_names` with the agent's own `tools` when present, never unions
      (FR-008)
- [X] T036 [US2] Pass `skill_matcher` into the orchestration `configurable` dict at invocation
      time in `apps/ze-api/ze_api/container.py` (or the graph-invocation call site), sourced
      from `build_skills_stack`
- [X] T037 [US2] Add `skills_used: list[SkillUsageTrace]` to the `trace_update` WS frame
      payload and `MessageTraceResponse` schema in `apps/ze-api/ze_api/api/schemas.py` (the
      dataclass field is included automatically via existing `**asdict(trace)`, per
      research.md §9 — verify no manual allowlist filters it out)
- [X] T038 [US2] Add `skills.match_threshold: 0.5` and `skills` block scaffolding to
      `apps/ze-api/config/config.yaml` per data-model.md Config additions
- [X] T039 [P] [US2] Extend `apps/ze-web/src/widgets/mind-panel/` trace panel component to
      render `skills_used` entries (name, source, trigger badge) alongside existing trace
      sections

**Checkpoint**: User Stories 1 AND 2 both work independently — quickstart.md Scenarios 4–5,
9 pass.

---

## Phase 5: User Story 3 - Manage installed skills (Priority: P2)

**Goal**: A single view lists every skill (bundled + imported) with source/status and lets the
user disable, re-enable, or remove one.

**Independent Test**: Import multiple skills into different states, confirm the management view
lists/filters them correctly and each state transition works.

### Tests for User Story 3

- [X] T040 [P] [US3] Unit tests for disable/enable/remove transitions in
      `core/ze-skills/tests/test_review.py` (extend) — `active → disabled`, `disabled →
      active` (no new `SkillReview` row per FR-013), `disabled → active` rejected if status
      drifted to `pending_review` in the meantime, `remove_skill` cascades and rejects on
      `source == bundled`
- [X] T041 [P] [US3] REST route tests for disable/enable/delete in
      `apps/ze-api/tests/api/routes/test_skills.py` (extend) — 409 on invalid-state
      transitions, 403/422 on deleting a bundled skill
- [X] T042 [P] [US3] Unit tests for bundled-skill startup registration in
      `core/ze-agents/tests/test_bootstrap.py` (extend) — each `ZePlugin.bundled_skill_paths()`
      entry is loaded and registered via `SkillStore` with `source=bundled`,
      `bundling_plugin` set to the owning plugin's identifier, `status=active` with no review
      gate; re-running startup against an already-registered bundled skill is idempotent
      (no duplicate row, matches `(slug, source)` uniqueness from T010)
- [X] T043 [P] [US3] Vitest tests for `apps/ze-web/src/widgets/skill-management/ui/
      SkillManagementList.test.tsx` — renders mixed-state list, triggers transitions,
      import form submission

### Implementation for User Story 3

- [X] T044 [US3] Implement `disable_skill`, `enable_skill`, `remove_skill` in
      `core/ze-skills/ze_skills/review.py` (conditional transitions per FR-013; `remove_skill`
      cascades `ReferenceFile`/`SkillReview` rows and raises for `source == bundled`, FR-014)
- [X] T045 [US3] Add `disable()`, `enable()`, `remove()` wrappers to
      `core/ze-skills/ze_skills/rest.py`
- [X] T046 [US3] Add `POST /api/v0/skills/{id}/disable`, `POST /api/v0/skills/{id}/enable`,
      `DELETE /api/v0/skills/{id}` routes to
      `apps/ze-api/ze_api/api/routes/skills.py` per contracts/skills-api.md
- [X] T047 [P] [US3] Implement `ZePlugin.bundled_skill_paths() -> list[str]` (default `[]`) in
      `core/ze-plugin/ze_plugin/plugin.py`
- [X] T048 [US3] Import bundled-skill modules at startup in
      `core/ze-agents/ze_agents/bootstrap.py` (mirrors `_plugin_agent_module_paths`) — for
      each plugin's `bundled_skill_paths()`, load and register the skill via `SkillStore` with
      `source=bundled`, `bundling_plugin=<plugin identifier>`, `status=active` (no review gate
      for developer-authored skills, consistent with FR-007)
- [X] T049 [P] [US3] Create `apps/ze-web/src/entities/skill/api/useSkillsQuery.ts`,
      `useSkillImportMutation.ts`, `useSkillTransitionMutation.ts` (approve/reject/disable/
      enable/remove), and `apps/ze-web/src/entities/skill/index.ts` barrel export
- [X] T050 [US3] Create `apps/ze-web/src/widgets/skill-management/ui/SkillManagementList.tsx`
      — list with source/status columns, import-from-URL action, per-row transition buttons
      (mirrors `widgets/loop-review` shape)
- [X] T051 [US3] Create `apps/ze-web/src/pages/skills/` management page and register its route
      in `apps/ze-web/src/shared/config/nav-routes.ts` + `apps/ze-web/src/app/router/routes.ts`

**Checkpoint**: User Stories 1, 2, AND 3 all work independently — quickstart.md Scenario 6
passes.

---

## Phase 6: User Story 4 - Skill content changes after import (Priority: P3)

**Goal**: An approved imported skill whose source content changes on refresh reverts to pending
review (old content preserved for comparison) and stays inert until re-approved; unreachable
sources don't deactivate it.

**Independent Test**: Import and approve a skill, change its source content, trigger a refresh,
confirm it reverts to pending review with both versions viewable, and confirm it's inert in
conversation until re-approved.

### Tests for User Story 4

- [X] T052 [P] [US4] Unit tests for `refresh_skill()` content-hash comparison in
      `core/ze-skills/tests/test_review.py` (extend) — changed content → `pending_review`
      revert with prior version retrievable, unchanged content → no status change,
      unreachable source → `last_check_error` set, `active` unchanged, no exception raised
      (spec Edge Cases)
- [X] T053 [P] [US4] Unit tests for `SkillRecheckJob` in
      `core/ze-skills/tests/jobs/test_recheck.py` — sweeps all imported skills regardless of
      `active`/`disabled` status, calls the same refresh logic per skill, mocked `httpx`
- [X] T054 [US4] REST route test for `POST /api/v0/skills/{id}/refresh` in
      `apps/ze-api/tests/api/routes/test_skills.py` (extend) — 200 with `pending_review` on
      change, 200 unchanged on no-op, 200 with `last_check_error` on unreachable source, 422
      on `source == bundled`

### Implementation for User Story 4

- [X] T055 [US4] Implement `refresh_skill()` in `core/ze-skills/ze_skills/review.py` —
      re-fetches `origin_url` via `fetch_skill_source()`, recomputes `content_hash`; on
      mismatch, transitions `active|disabled|rejected → pending_review` and preserves the
      previously-approved `SkillReview` for comparison (FR-015, FR-016); on fetch failure,
      sets `last_check_error` and updates `last_checked_at` without changing `status` (spec
      Edge Cases); always updates `last_checked_at` on success too; rejects for
      `source == bundled`
- [X] T056 [US4] Add `refresh()` wrapper to `core/ze-skills/ze_skills/rest.py` and
      `POST /api/v0/skills/{id}/refresh` route to
      `apps/ze-api/ze_api/api/routes/skills.py`
- [X] T057 [US4] Extend `GET /api/v0/skills/{id}` detail response/schema to include
      `previous_version` (from the latest approved `SkillReview`) when
      `status == pending_review` and a prior approval exists (FR-016)
- [X] T058 [US4] Implement `SkillRecheckJob` (`@proactive_job`) in
      `core/ze-skills/ze_skills/jobs/recheck.py` — daily cron sweep over all `source=imported`
      skills calling `refresh_skill()` per skill, cron read from `skills.recheck.cron`
      (default `"0 6 * * *"`)
- [X] T059 [US4] Add `register_proactive_jobs(scheduler, settings, stack)` to
      `core/ze-skills/ze_skills/bootstrap.py` wiring `SkillRecheckJob`, honoring
      `skills.recheck.enabled`
- [X] T060 [US4] Call `ze_skills` job registration from
      `apps/ze-api/ze_api/compose.py`'s proactive job fan-out
- [X] T061 [US4] Add `skills.recheck.enabled`/`skills.recheck.cron` to
      `apps/ze-api/config/config.yaml` (already scaffolded in T038 — extend with recheck
      block)

**Checkpoint**: All four user stories independently functional — quickstart.md Scenarios 7–8
pass; SC-004 satisfied.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and full validation across all stories.

- [ ] T062 [P] Update `CLAUDE.md`'s package dependency graph, migration-ownership table, and
      Phase status table with the new `ze-skills` entry and Phase 114 row
- [ ] T063 [P] Add `core/ze-skills/README.md` (mirrors `core/ze-worldstate/README.md` — package
      purpose, key modules, how bundled vs. imported skills flow through the system)
- [ ] T064 Run `make lint` and `make format` across all touched packages
      (`ze-skills`, `ze-core`, `ze-agents`, `ze-plugin`, `ze-api`, `ze-web`)
- [ ] T065 Run `make test-skills`, `make test-core`, `make test-agents`,
      `make test` (ze-api), `make test-web` — confirm all pass
- [ ] T066 Execute quickstart.md Scenarios 1–9 end-to-end against a running `make dev` +
      `make db-up && make migrate` stack; confirm every "Expect" assertion holds

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories (types, schema, store
  are shared by every story).
- **User Story 1 (Phase 3)**: Depends on Foundational only. No dependency on US2/US3/US4.
- **User Story 2 (Phase 4)**: Depends on Foundational; consumes `Skill`/`SkillStore` from
  Foundational and the import/approve flow's *data* (an `active` skill) from US1 to be
  meaningfully testable end-to-end, but its own code (matching, graph node, tool-narrowing) has
  no US1 file dependency — can be built in parallel with US1 and integration-tested once both
  land.
- **User Story 3 (Phase 5)**: Depends on Foundational; extends `review.py`/`rest.py`/routes
  started in US1 (same files) — sequence after US1 to avoid merge conflicts, though logically
  independent.
- **User Story 4 (Phase 6)**: Depends on Foundational; extends `review.py`/`rest.py`/routes and
  config scaffolding from US1–US3 (same files) — sequence last among the stories.
- **Polish (Phase 7)**: Depends on all four user stories being complete.

### Within Each User Story

- Tests before implementation where both are listed (write tests first per repo's Test
  Discipline; the format doesn't gate implementation on a failing-test run for this feature,
  but tests must exist and pass by the story's checkpoint).
- Types/parser/importer before store-dependent orchestration before REST routes before web UI.
- Story complete before moving to the next priority.

### Parallel Opportunities

- T002, T003 in Setup can run in parallel with each other (after T001); T005 (Makefile target)
  can run in parallel with T002–T004.
- T006, T007 in Foundational can run in parallel (different files); T013, T014 can run in
  parallel with each other once T006/T012 land.
- T015, T016, T017 (US1 tests) can run in parallel; T018 depends on T019–T024 existing to have
  something to test against in practice, but can be written in parallel and run red-then-green.
- T027, T028, T029 (US2 tests) can run in parallel (different files).
- T039 (web trace panel) can run in parallel with backend US2 tasks once T037's payload shape is
  fixed.
- T040, T041, T042, T043 (US3 tests) can run in parallel.
- T047 (`bundled_skill_paths()` hook) can run in parallel with T044–T046.
- T049 (web API hooks) can run in parallel with T044–T048 (backend).
- T052, T053 (US4 tests) can run in parallel.
- T062, T063 (docs) can run in parallel with each other and with T064–T066.

---

## Parallel Example: User Story 1

```bash
# Launch US1 tests together:
Task: "Unit tests for parse_skill_md() in core/ze-skills/tests/test_parser.py"
Task: "Unit tests for fetch_skill_source() in core/ze-skills/tests/test_importer.py"
Task: "Unit tests for approve/reject transitions in core/ze-skills/tests/test_review.py"

# Then implementation, respecting the parser -> importer -> review -> rest -> routes chain:
Task: "Implement parse_skill_md() in core/ze-skills/ze_skills/parser.py"
Task: "Implement fetch_skill_source() in core/ze-skills/ze_skills/importer.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks everything)
3. Complete Phase 3: User Story 1 — import, review, approve/reject via REST
4. **STOP and VALIDATE**: quickstart.md Scenarios 1–3 pass independently
5. Deploy/demo if ready — a working import+review pipeline with no conversational effect yet

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. User Story 1 → validate → MVP (skills can be imported and approved, but do nothing yet)
3. User Story 2 → validate → skills now visibly shape conversations (the feature's real payoff)
4. User Story 3 → validate → skills are manageable at scale, bundled skills supported
5. User Story 4 → validate → trust is preserved across source content drift
6. Polish → docs, lint, full test run, full quickstart pass

### Parallel Team Strategy

With multiple developers, after Foundational (Phase 2) completes:

- Developer A: User Story 1 (import/parse/review/REST)
- Developer B: User Story 2 (matching/graph node/tool-narrowing) — can start immediately since
  it depends on Foundational's `Skill`/`SkillStore`, not on US1's REST routes; integration-test
  against US1's approve flow once both land
- Developer C: starts User Story 3/4 scaffolding (web entity hooks, `bundled_skill_paths()`
  hook) that don't touch the shared `review.py`/`rest.py`/`routes/skills.py` files US1 owns,
  then rebases onto those files once US1 lands

---

## Notes

- [P] tasks touch different files with no unfinished-task dependency.
- [Story] labels map every user-story-phase task to US1–US4 for traceability back to spec.md.
- `review.py`, `rest.py`, and `apps/ze-api/ze_api/api/routes/skills.py` are shared files
  extended across US1/US3/US4 — sequence those stories' tasks against each other to avoid
  conflicting edits even though they're logically independent.
- Commit after each task or logical group; stop at any checkpoint to validate a story in
  isolation before continuing.
- Avoid: vague tasks, same-file conflicts within a single [P] batch, cross-story dependencies
  that would break independent testability.
