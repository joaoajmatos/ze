---
description: "Task list for Workspace Environment (phase 115)"
---

# Tasks: Workspace Environment

**Input**: Design documents from `/specs/phases/115-workspace-sidecar/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/workspace-api.md,
contracts/workspace-sidecar.md, quickstart.md

**Tests**: Included per constitution Test Discipline and plan.md §Testing (pytest for
`ze-workspace` / sidecar fakes / `ze-skills` / ze-api routes; vitest for workspace page,
ConfirmBar edit, message chip). Not a strict red-then-green gate; every implementation task
that adds testable logic has a paired test task in the same story phase.

**Organization**: Phases are Setup → Foundational → one phase per user story (P1/P1/P2/P3) →
Polish. Within a phase, **waves** are independent (different files); join lines mark what
must finish before the next wave.

**Analyze remediations (2026-08-14)**: `ToolConfirmationRequired` lives in `ze-agents`
(C1); unattended gating stays in `ze-automation` via injection (C2); ingest pipeline is
injected, no `ze-ingestion` dep (I1); output denylist sanitizer (G1); sidecar split into
three sequential tasks (U1); `GET /workspace/runs` in US1 REST (I2); `import
ze_workspace.tools` in bootstrap (U3); sidecar tests under `core/ze-workspace/tests/`
(U4).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Independent of other tasks in the same wave (different file, no unfinished dependency)
- **[Story]**: US1 (conversation computer + files + modes), US2 (skill scripts), US3
  (workspace view), US4 (unattended Auto)
- Every task names an exact file path

## Path Conventions

Existing monorepo — new `core/ze-workspace/` and `sidecar/workspace/`; extend `core/ze-skills/`,
`core/ze-agents/`, `core/ze-core/`, `core/ze-automation/`, `apps/ze-api/`, `apps/ze-web/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold the package, sidecar skeleton, and wiring hooks so later phases have a
place to land code.

**Wave 1 — package manifest:**

- [x] T001 Create `core/ze-workspace/pyproject.toml` (deps: `ze-agents`, `ze-logging`,
      `ze-data`, `httpx`, `asyncpg==0.31.0` — **not** `ze-ingestion`; dev group mirrors
      `core/ze-skills/pyproject.toml`; `[tool.hatch.build.targets.wheel] packages =
      ["ze_workspace"]`; `testpaths = ["tests"]`, `asyncio_mode = "auto"`)

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 — independent (different files):**

- [x] T002 [P] Create `core/ze-workspace/ze_workspace/__init__.py` (empty package marker)
- [x] T003 [P] Create `core/ze-workspace/tests/__init__.py` and
      `core/ze-workspace/tests/conftest.py` (mock asyncpg pool, fake sidecar `httpx` app —
      mirrors `core/ze-browser/tests` + `core/ze-skills/tests/conftest.py`)
- [x] T004 [P] Scaffold `sidecar/workspace/` with `Dockerfile`, `fly.toml` (app
      `ze-workspace`, volume, `min_machines_running = 1`, `internal_port = 8080`),
      `requirements.txt` (fastapi/uvicorn), and `README.md` (mirrors `sidecar/browser/`)

**⟶ Wait for Wave 2 to finish, then:**

**Wave 3 — composition root + local deploy:**

- [x] T005 Add `ze-workspace` to `apps/ze-api/pyproject.toml` dependencies and
      `[tool.uv.sources]` (`ze-workspace = { workspace = true }`)
- [x] T006 [P] Add `test-workspace` to the root `Makefile` (`.PHONY`, `TEST_PY_PACKAGES`,
      `make help`) pointing at `core/ze-workspace/tests`, and a row in `docs/testing.md`
- [x] T007 [P] Add Compose service `workspace` (build `sidecar/workspace`, named volume
      `workspace_data`, healthcheck `GET /health`) and `WORKSPACE_SERVICE_URL:
      http://workspace:8080` on `backend` in `docker-compose.yml`
- [x] T008 [P] Add `workspace_service_url`, `workspace_api_token`,
      `workspace_timeout_seconds` to `apps/ze-api/ze_api/settings.py`; document in
      `apps/ze-api/.env.example`; add `workspace:` block (timeout, preview chars, ceiling,
      lock wait) to `apps/ze-api/config/config.yaml`

**Checkpoint**: `uv sync` resolves `ze-workspace`; `make test-workspace` runs (0 tests);
Compose file lists the sidecar. No domain logic yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Types, errors, schema, store, client, gate, sidecar control API, sanitizer, and
container injection. No user-story work until this phase is complete.

**⚠️ CRITICAL**: BLOCKS all user stories.

**Wave 1 — independent types:**

- [x] T009 [P] Define `WorkspaceMode`, `WorkspaceRunStatus`, `WorkspaceRunOrigin`
      (`conversation` | `user` | `unattended`), `WorkspaceAction` StrEnums and
      `WorkspaceRun`, `WorkspaceFile`, `WorkspaceState` dataclasses in
      `core/ze-workspace/ze_workspace/types.py` (per data-model.md)
- [x] T010 [P] Define `WorkspaceUnavailableError`, `WorkspaceBusyError`,
      `WorkspaceFullError`, `WorkspacePathError`, `WorkspaceNotFoundError` in
      `core/ze-workspace/ze_workspace/errors.py` (subclass `ZeError`). Do **not** put a
      confirm-interrupt type here.
- [x] T011 [P] Add `ToolConfirmationRequired(AgentError)` next to `ToolBlockedError` in
      `core/ze-agents/ze_agents/errors.py` — payload: prompt, editable flag, proposed
      command or file contents. `ze_core` / `ze_agents` never import `ze_workspace`.
- [x] T012 [P] Add `WorkspaceUsageTrace` and `MessageTrace.workspace`; add
      `SkillUsageTrace.script_ran: bool = False` in
      `core/ze-core/ze_core/conversation/messages/types.py`

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 — persistence + client + gate:**

- [x] T013 Create `core/ze-workspace/ze_workspace/migrations/env.py` (mirror
      `core/ze-skills/ze_skills/migrations/env.py`) and
      `core/ze-workspace/ze_workspace/migrations/versions/zws001_workspace.py` — raw SQL
      `workspace_state` (singleton `id=1`, default mode `ask`) and `workspace_runs` per
      data-model.md
- [x] T014 Register `_ZE_WORKSPACE_VERSIONS` in `apps/ze-api/ze_api/migrate.py` alongside
      `_ZE_SKILLS_VERSIONS`
- [x] T015 Implement `WorkspaceStore` protocol + `PostgresWorkspaceStore` in
      `core/ze-workspace/ze_workspace/store.py` — get/set mode, insert/list runs (including
      `origin` filter), update `last_used_at` / `last_reset_at`
- [x] T016 [P] Implement `WorkspaceClient` in `core/ze-workspace/ze_workspace/client.py`
      (`httpx` → sidecar contract in `contracts/workspace-sidecar.md`: health, stat, fs,
      run, cancel, reset; maps HTTP errors to `ze_workspace.errors`)
- [x] T017 [P] Implement `WorkspaceGate` in `core/ze-workspace/ze_workspace/gate.py` —
      mode × action × origin → `allow` | `confirm` | `plan` | `deny` per data-model.md
      (`origin=conversation` Off denies all tools; `origin=user` REST list/read/place/
      retrieve allow even in Off; unattended commands only `auto`; unattended writes
      `auto_edit`|`auto`; reset always confirm)

**⟶ Wait for Wave 2 to finish, then:**

**Wave 3 — sidecar HTTP + filesystem jail** (same tree, sequential with 4–5):

- [x] T018 Implement sidecar HTTP + path jail in `sidecar/workspace/main.py` —
      `/health`, `/stat`, `/fs*` (list/download/upload/put/delete); unprivileged paths
      refuse escape (FR-015); storage ceiling on writes (FR-020); no `/run` yet

**⟶ Wait for Wave 3 to finish, then:**

**Wave 4 — sidecar exec:**

- [x] T019 Implement `/run`, `/cancel`, mutex, timeout in `sidecar/workspace/supervisor.py`
      and wire from `sidecar/workspace/main.py` — `run_lock_wait_seconds` then 409 busy
      (FR-019); SIGTERM/KILL on `run_timeout_seconds` (FR-009); stdout spill file when over
      `output_preview_chars`; image includes bash, coreutils, curl, python3, node (FR-016)

**⟶ Wait for Wave 4 to finish, then:**

**Wave 5 — sidecar isolation:**

- [x] T020 Strip child env and deny private-range egress in
      `sidecar/workspace/supervisor.py` — clean env only (`PATH`, `HOME=/workspace`,
      `LANG`); never inherit `WORKSPACE_API_TOKEN` or Ze secrets; nftables/iptables
      owner-uid deny RFC1918 + Fly 6PN; public egress allowed (FR-003, FR-026)

**⟶ Wait for Wave 5 to finish, then:**

**Wave 6 — sanitizer + wiring:**

- [x] T021 [P] Implement `redact()` in `core/ze-workspace/ze_workspace/sanitize.py` and
      call it from `PostgresWorkspaceStore` insert/update of `output_preview` /
      `error_summary` plus any chat-inline helper — denylist env-key names
      (`OPENROUTER_API_KEY`, `DATABASE_URL`, `ZE_API_KEY`, `WORKSPACE_API_TOKEN`,
      `*_SECRET`/`*_TOKEN`/`*_PASSWORD`) (SC-004)
- [x] T022 Create `build_workspace_stack` in `core/ze-workspace/ze_workspace/bootstrap.py`
      — `import ze_workspace.tools  # noqa: F401` so `@tool` registers; construct client +
      store + gate; put `WorkspaceClient` / `WorkspaceGate` / `IngestionPipeline` (from
      shared container, do not import-construct here if it creates a package dep) on
      `dep_map` and `configurable["workspace_gate"]` / `workspace_client`. Wire in
      `apps/ze-api/ze_api/container.py` (`close()` the client). `ze_core` must not import
      `ze_workspace`.

**⟶ Wait for Wave 6 to finish, then:**

**Wave 7 — foundational tests (independent files):**

- [x] T023 [P] Unit tests for `PostgresWorkspaceStore` in
      `core/ze-workspace/tests/test_store.py` (mock asyncpg; mode persist; run insert/list
      with origin filter)
- [x] T024 [P] Unit tests for `WorkspaceGate` in `core/ze-workspace/tests/test_gate.py` —
      conversation Off denies list; user REST list allows in Off; unattended run only
      Auto; unattended write Auto-edit or Auto; reset-always-confirm
- [x] T025 [P] Unit tests for `WorkspaceClient` in
      `core/ze-workspace/tests/test_client.py` using a fake HTTP sidecar (health false →
      `WorkspaceUnavailableError`; 409 busy/full; 400 outside_workspace)
- [x] T026 [P] Sidecar contract tests in
      `core/ze-workspace/tests/test_sidecar_contract.py` (fake supervisor, **not**
      `sidecar/workspace/tests/`) — path escape refused; child env lacks token/secrets;
      second run busy; ceiling refuse leaves tree unchanged
- [x] T027 [P] Unit tests for `redact()` in `core/ze-workspace/tests/test_sanitize.py` —
      command output containing `OPENROUTER_API_KEY=...` is not present in the returned
      preview

**Checkpoint**: Schema, gate, client, sidecar slices, sanitizer, and injection exist and
are tested. User-story work can begin.

---

## Phase 3: User Story 1 - Ask Ze to do real work and get files back (Priority: P1) 🎯 MVP

**Goal**: In a conversation, Ze can create/read/update/list/delete files and run commands in
the workspace, honoring Off / Plan / Ask / Auto-edit / Auto (including persist and confirm /
edit), annotating the turn, placing chat attachments without ingesting, and degrading when
the sidecar is down. Runs complete in-turn and are persisted.

**Independent Test**: Ask Ze to create a named file with known contents (Ask mode → confirm),
retrieve it, disconnect and return — file still there. Also: deny does nothing; Auto-edit
writes without confirm but commands still confirm; Off refuses; unavailable does not
fabricate success.

### Tests for User Story 1

**Wave 1 — independent tests:**

- [x] T028 [P] [US1] Unit tests for workspace `@tool`s in
      `core/ze-workspace/tests/test_tools.py` — list/read/write/delete/run; Off deny; Plan
      dry-run (no client execute); Ask raises `ToolConfirmationRequired`; Auto-edit write
      vs run; truncated output spills to a file path (FR-009); ingest uses injected
      pipeline mock (no `ze_ingestion` import required in the test harness)
- [x] T029 [P] [US1] Unit tests for in-node confirm resume in
      `core/ze-core/tests/orchestration/test_workspace_interrupt.py` — catch
      `ToolConfirmationRequired` from `ze_agents.errors` (assert the test file does not
      import `ze_workspace`); approve executes edited payload; deny does not call sidecar;
      interrupt uses `pending_confirmations`
- [x] T030 [P] [US1] REST tests in `apps/ze-api/tests/api/routes/test_workspace.py` —
      get status/mode, PATCH mode persists, list/get/upload (dedupe name, 409 full, 400
      escape), `GET /workspace/runs`, ingest endpoint calls pipeline with `file_bytes` and
      does not delete the workspace file
- [x] T031 [P] [US1] Vitest for ConfirmBar edit + workspace chip in
      `apps/ze-web/src/entities/message/ui/ConfirmBar.test.tsx` and
      `apps/ze-web/src/entities/message/ui/MessageBubble.test.tsx`

**⟶ Wait for Wave 1 to finish, then:**

### Implementation for User Story 1

**Wave 2 — tools + platform merge:**

- [x] T032 [US1] Implement `@tool`s `workspace_list`, `workspace_read`, `workspace_write`,
      `workspace_delete`, `workspace_run`, `ingest_workspace_file` in
      `core/ze-workspace/ze_workspace/tools.py` — consult `WorkspaceGate`; Plan returns
      preview; Ask/confirm raises `ToolConfirmationRequired` from `ze_agents.errors`; Auto
      executes via `WorkspaceClient`; persist `WorkspaceRun` on `/run` after `redact()`
      (FR-008, FR-025, SC-004); `ingest_workspace_file` reads sidecar bytes and calls the
      **injected** `IngestionPipeline.ingest` (FR-028) — do not import `ze_ingestion` at
      module top if that implies a package dep; never auto-ingest on write/place (FR-021)
- [x] T033 [US1] Merge fixed `WORKSPACE_TOOLS` into `BaseAgent.agentic_loop` in
      `core/ze-agents/ze_agents/base_agent.py` (opt-out flag); skills still intersect, never
      union (FR-017). Catch `ToolConfirmationRequired` in `call_tool` and re-raise for the
      graph (do not import `ze_workspace`).

**⟶ Wait for Wave 2 to finish, then:**

**Wave 3 — confirm interrupt + resume:**

- [x] T034 [US1] In `core/ze-core/ze_core/orchestration/nodes/execution.py`, map
      `ToolConfirmationRequired` (from `ze_agents.errors` only) to LangGraph `interrupt()`;
      write `pending_confirmations`; on resume run the approved or `edited_content` payload.
      Extend `core/ze-core/ze_core/conversation/turn.py` `resume_turn` to pass
      `Command(resume=...)`. Keep existing `interrupt_before=["await_confirmation"]`
      CapabilityGate path unchanged. This file must not import `ze_workspace`.

**⟶ Wait for Wave 3 to finish, then:**

**Wave 4 — REST + schemas:**

- [x] T035 [US1] Add Workspace Pydantic schemas and extend `WsConfirmFrame.edited_content`,
      `WsSendMessageFrame.context.workspace_placed`, `MessageTraceResponse.workspace`,
      `SkillUsageTraceResponse.script_ran` in `apps/ze-api/ze_api/api/schemas.py` per
      `contracts/workspace-api.md`
- [x] T036 [US1] Implement `core/ze-workspace/ze_workspace/rest.py` facade (plain dicts) and
      `apps/ze-api/ze_api/api/routes/workspace.py` — `GET /workspace`, `GET/PATCH
      /workspace/mode`, `GET/POST /workspace/files`, `GET/DELETE
      /workspace/files/{path}`, `POST /workspace/files/{path}/ingest`, `GET
      /workspace/runs`; map errors to 503/409/400/404; mount in
      `apps/ze-api/ze_api/api/app.py`. Upload is place-only (FR-027). Duplicate names
      suffix, do not overwrite. REST file ops use `origin=user`.

**⟶ Wait for Wave 4 to finish, then:**

**Wave 5 — WS, trace, chat UI:**

- [x] T037 [US1] Handle `edited_content` on confirm in
      `apps/ze-api/ze_api/api/websocket/confirmation.py` and
      `apps/ze-web/src/features/respond-to-confirmation/api/useConfirmation.ts` +
      `apps/ze-web/src/entities/message/ui/ConfirmBar.tsx` (`editable: true` shows an edit
      field). Show current mode on the confirm prompt (FR-029).
- [x] T038 [US1] Populate `MessageTrace.workspace` in
      `core/ze-core/ze_core/orchestration/nodes/trace.py`; emit on `trace_update`. Add
      `WorkspaceSection` in `apps/ze-web/src/widgets/trace-panel/ui/WorkspaceSection.tsx`
      and a visible chip on
      `apps/ze-web/src/entities/message/ui/MessageBubble.tsx` (FR-007, SC-002 — not
      trace-only).
- [x] T039 [US1] Add composer attachment in
      `apps/ze-web/src/entities/message/ui/ChatInput.tsx` — REST
      `uploadWorkspaceFile` then send `context.workspace_placed` (bytes never on WS).
      Unavailable sidecar: tools raise `WorkspaceUnavailableError`; turn warns, no
      fabricated success (FR-010).

**Checkpoint**: User Story 1 independently testable — quickstart Scenarios 1–9, 12, 14
(timeout/busy) pass. Mode persists across reconnect (Scenario 5). In-turn only (FR-024):
no detach, follow-up turn, or completion push.

---

## Phase 4: User Story 2 - Approved skill scripts actually run (Priority: P1)

**Goal**: Bundled skill scripts are stored, shown at review, and run in the workspace only
after a separate executable approval. Phase 114 instructions-only approvals stay
non-executing. Scripts follow the same mode rules as commands (FR-030).

**Independent Test**: Approve a skill with a script as instructions only — script does not
run. `POST .../approve-executables`, invoke in Auto — distinctive file appears; turn
annotated with skill **and** `script_ran`. Disabled/pending skills never run scripts.

### Tests for User Story 2

**Wave 1 — independent tests:**

- [x] T040 [P] [US2] Update importer/parser tests in
      `core/ze-skills/tests/test_importer.py` and `core/ze-skills/tests/test_parser.py` —
      script files are stored (not discarded); `has_scripts` true; instructions-only
      approve leaves `executable_approved` false
- [x] T041 [P] [US2] Unit tests for `approve_skill_executables` in
      `core/ze-skills/tests/test_review.py` — sets flag only when `has_scripts`; content
      change of scripts clears flag and reverts pending_review; disabled skill scripts do
      not run
- [x] T042 [P] [US2] Tests for `workspace_run_skill_script` in
      `core/ze-workspace/tests/test_tools.py` (extend) — refuses without
      `executable_approved`; Off/Plan do not execute; Ask confirms; Auto runs; materializes
      from DB bytes not origin_url
- [x] T043 [P] [US2] REST test `POST /api/v0/skills/{id}/approve-executables` in
      `apps/ze-api/tests/api/routes/test_skills.py`; vitest that
      `apps/ze-web/src/widgets/skill-management/ui/SkillManagementList.test.tsx` shows
      script warning + executable-approval action distinct from Approve (FR-013)

**⟶ Wait for Wave 1 to finish, then:**

### Implementation for User Story 2

**Wave 2 — persist scripts:**

- [x] T044 [US2] Add `zsk002_skill_scripts.py` in
      `core/ze-skills/ze_skills/migrations/versions/` — rename
      `has_unsupported_scripts` → `has_scripts`; add `executable_approved`,
      `executable_approved_at`; create `skill_scripts` (BYTEA, unique `(skill_id,
      filename)`). Update `core/ze-skills/ze_skills/types.py` and `store.py`.

**⟶ Wait for Wave 2 to finish, then:**

**Wave 3 — import + approve-executables:**

- [x] T045 [US2] Change `core/ze-skills/ze_skills/importer.py` to persist script files
      instead of skipping them; keep non-script refs on `skill_reference_files`. Update
      `review.py` `approve_skill` so it MUST NOT set `executable_approved` (FR-012,
      SC-005). Add `approve_skill_executables`. Recheck that changes script bytes clears
      executable approval and reverts `pending_review`. Snapshot includes `has_scripts` +
      script filenames.
- [x] T046 [US2] Add `approve_executables()` wrapper +
      `POST /api/v0/skills/{id}/approve-executables` (`operation_id=approveSkillExecutables`)
      in `core/ze-skills/ze_skills/rest.py` and
      `apps/ze-api/ze_api/api/routes/skills.py`. Replace `has_unsupported_scripts` with
      `has_scripts`, `executable_approved`, `script_filenames` on skill schemas in
      `apps/ze-api/ze_api/api/schemas.py`. Run `make codegen`.

**⟶ Wait for Wave 3 to finish, then:**

**Wave 4 — run script tool + UI + trace:**

- [x] T047 [US2] Implement `workspace_run_skill_script` in
      `core/ze-workspace/ze_workspace/tools.py` — require skill `active` +
      `executable_approved`; apply `WorkspaceGate` as for `run` (FR-030); materialize
      script bytes to a temp path under `/workspace` and `POST /run`; record
      `skill_id` / `skill_script_path` on `workspace_runs`; set
      `SkillUsageTrace.script_ran` via trace state
- [x] T048 [P] [US2] Surface scripts + executable approval on
      `apps/ze-web/src/widgets/skill-management/ui/SkillManagementList.tsx` (and entity
      mutation `approveSkillExecutables` in
      `apps/ze-web/src/entities/skill/api/useSkillTransitionMutation.ts`). Extend
      `apps/ze-web/src/widgets/trace-panel/ui/SkillsSection.tsx` to show `script_ran`.

**Checkpoint**: User Stories 1 and 2 work independently — quickstart Scenario 10; SC-005
(zero silent promotions).

---

## Phase 5: User Story 3 - Inspect, retrieve, and reset the workspace (Priority: P2)

**Goal**: A System page lists workspace files, accepts uploads, retrieves bytes, and resets
to empty after confirmation. Reset never wipes under a live writer without saying so.
Works even when mode is Off (user-initiated REST).

**Independent Test**: Create files via conversation, open `/workspace`, upload a named file,
retrieve it, confirm reset, listing empty. Reset without confirm leaves files.

### Tests for User Story 3

**Wave 1 — independent tests:**

- [x] T049 [P] [US3] REST tests for `POST /api/v0/workspace/reset` in
      `apps/ze-api/tests/api/routes/test_workspace.py` (extend) — issues confirm; approve
      cancels in-flight run then wipes; deny unchanged; list/upload still work when mode is
      Off
- [x] T050 [P] [US3] Vitest for
      `apps/ze-web/src/widgets/workspace-management/ui/WorkspaceManagement.test.tsx` —
      listing names/sizes/mtimes, upload, retrieve, reset confirm, mode switcher

**⟶ Wait for Wave 1 to finish, then:**

### Implementation for User Story 3

**Wave 2 — reset API:**

- [x] T051 [US3] Implement `POST /api/v0/workspace/reset` in
      `apps/ze-api/ze_api/api/routes/workspace.py` + `ze_workspace/rest.py` — always
      confirm (`editable: false`); on approve, sidecar `/cancel` then `/reset`; set
      `workspace_state.last_reset_at` (FR-014)

**⟶ Wait for Wave 2 to finish, then:**

**Wave 3 — web System page:**

- [x] T052 [P] [US3] Create `apps/ze-web/src/entities/workspace/` query/mutation hooks
      (`useWorkspaceQuery`, `useWorkspaceFilesQuery`, `useWorkspaceRunsQuery`,
      `useWorkspaceModeMutation`, `useWorkspaceUploadMutation`,
      `useWorkspaceResetMutation`) + `index.ts`; add `queryKeys.workspace*` in
      `apps/ze-web/src/shared/lib/query-keys.ts`
- [x] T053 [US3] Create `apps/ze-web/src/widgets/workspace-management/ui/` listing +
      upload + retrieve + reset + mode switcher; thin
      `apps/ze-web/src/pages/workspace/ui/WorkspacePage.tsx`; register `workspace` in
      `apps/ze-web/src/shared/config/nav-routes.ts` (`systemNavRoutes`) and
      `apps/ze-web/src/app/router/routes.ts`. Mode switcher also visible when a workspace
      confirm is pending (FR-029).

**Checkpoint**: User Stories 1–3 independently functional — quickstart Scenario 11, SC-006.

---

## Phase 6: User Story 4 - Background work may use the same workspace (Priority: P3)

**Goal**: Unattended goals/workflows may run workspace commands only when mode is Auto.
Auto-edit may write files unattended but is not enough for unattended commands. Results
show as `origin=unattended` runs. Gating lives in `ze-automation` only.

**Independent Test**: Mode Auto, trigger a scheduled step that writes a known file while the
chat app is disconnected — file present, run listed as unattended. Repeat in Ask — no file.

### Tests for User Story 4

**Wave 1:**

- [x] T054 [P] [US4] Unit tests in
      `core/ze-automation/tests/test_workspace_unattended.py` — Ask/Plan/Off skip
      unattended `run`/`run_script`; Auto-edit skips unattended commands but may write;
      Auto may run; persisted run `origin` is `unattended`. Tests inject a fake
      `WorkspaceGate` — do not import from `ze_personal`.

**⟶ Wait for Wave 1 to finish, then:**

### Implementation for User Story 4

**Wave 2:**

- [x] T055 [US4] Consult injected `WorkspaceGate` with `origin=unattended` from
      `core/ze-automation/ze_automation/goals/executor.py` and
      `core/ze-automation/ze_automation/workflow/` (scheduler/executor) **before**
      workspace tools run. Do not change non-workspace `GateDecision.EXECUTE` bypass.
      Do **not** add a `ze_workspace` import to `ze_personal/graph/workflow.py` or any
      plugin. Record runs with `origin=unattended` (FR-018).
- [x] T056 [US4] Show `origin` on
      `apps/ze-web/src/widgets/workspace-management/` recent-activity section using
      `GET /api/v0/workspace/runs` (route already in T036) (User Story 4 scenario 3).

**Checkpoint**: All four stories independently functional — quickstart Scenario 13.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Docs, codegen, lint/tests, and Success Criteria validation. Isolation
invariants and “do not” requirements (FR-022 browser stays separate, FR-023 mind stays put,
FR-024 no detach) are confirmed here.

**Wave 1 — independent docs:**

- [x] T057 [P] Update `CLAUDE.md` / `AGENTS.md` package graph, migration-ownership table
      (`zws`, `zsk002`), graph flow if needed, and Phase 115 status row. Note:
      `ze-core`/`ze-agents` must not depend on `ze-workspace`.
- [x] T058 [P] Add `core/ze-workspace/README.md` and `docs/workspace.md` (mirrors
      `docs/browser.md` — env vars, isolation rules, mode table, not a browsing session)
- [x] T059 [P] Update `specs/README.md` index row for 115; keep spec header Status in sync
      when implementation lands

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 — validation (single owner; no `owns: validation` hook in companion.yml):**

- [ ] T060 Run `make codegen` if schema changed; `make lint` and `make format` on touched
      packages (`ze-workspace`, `ze-skills`, `ze-core`, `ze-agents`, `ze-automation`,
      `ze-api`, `ze-web`)
- [ ] T061 Run `make test-workspace`, `make test-skills`, `make test-core`,
      `make test-agents`, `make test-automation`, `make test` (ze-api), `make test-web`
- [ ] T062 Execute `specs/phases/115-workspace-sidecar/quickstart.md` Scenarios 1–14
      against `make db-up && make migrate && make dev-full` with the workspace sidecar
      healthy; confirm every Expect, including SC-001–SC-008 (SC-004: no secrets in
      shown output)

**Checkpoint**: Feature ready to mark implemented after T062.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: start immediately
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all stories
- **US1 (Phase 3)**: depends on Foundational only — MVP
- **US2 (Phase 4)**: depends on Foundational; needs US1 tools/sidecar to actually execute
  scripts end-to-end, but `zsk002` / importer / approve-executables can start in parallel
  with US1 UI
- **US3 (Phase 5)**: depends on Foundational; extends `routes/workspace.py` from US1 —
  sequence after US1 to avoid same-file conflicts
- **US4 (Phase 6)**: depends on Foundational + US1 tools/gate; sequence after US1
- **Polish**: depends on all desired stories

### Waves (one-line restatement)

- P1: T001 → T002–T004 → T005–T008
- P2: T009–T012 → T013–T017 → T018 → T019 → T020 → T021–T022 → T023–T027
- US1: T028–T031 → T032–T033 → T034 → T035–T036 → T037–T039
- US2: T040–T043 → T044 → T045–T046 → T047–T048
- US3: T049–T050 → T051 → T052–T053
- US4: T054 → T055–T056
- Polish: T057–T059 → T060–T062

### User story independence

- **US1**: conversation computer; no dependency on skills executable path
- **US2**: independently testable once a workspace exists (Foundational + US1 run tool)
- **US3**: independently testable with files from US1 or REST upload
- **US4**: independently testable by toggling mode and triggering one unattended write

---

## Parallel opportunities

- Setup Wave 2 (T002–T004) after T001
- Foundational Wave 1 (T009–T012) in parallel; Wave 7 tests (T023–T027) in parallel
- Sidecar T018 → T019 → T020 are **sequential** (same files)
- US1 tests T028–T031 in parallel; T037–T039 after REST contract is stable
- US2 tests T040–T043 in parallel; T048 (web) parallel with T047 once API fields exist
- US3 T052 (entities) parallel with T051 (reset route)
- Polish T057–T059 in parallel

---

## Parallel example: User Story 1 tests

```text
Task: core/ze-workspace/tests/test_tools.py
Task: core/ze-core/tests/orchestration/test_workspace_interrupt.py
Task: apps/ze-api/tests/api/routes/test_workspace.py
Task: ConfirmBar.test.tsx + MessageBubble.test.tsx
```

---

## Implementation strategy

### MVP (User Story 1 only)

1. Phase 1 Setup
2. Phase 2 Foundational (blocks everything)
3. Phase 3 US1 — files, commands, modes, confirm, attach, annotation
4. **STOP and VALIDATE** quickstart Scenarios 1–9, 12, 14
5. Demo: Ze can do computer work in a turn and you can get the file back

### Incremental delivery

1. Setup + Foundational
2. US1 → MVP
3. US2 → skills scripts actually run after re-approval
4. US3 → workspace is inspectable and resettable
5. US4 → 24/7 hands when mode is Auto
6. Polish → docs, lint, full quickstart

### Parallel team (after Foundational)

- A: US1 tools + interrupt + REST
- B: US2 zsk002 + importer + approve-executables (rebase onto US1 tools for T047)
- C: US3 web page scaffolding (entities/routes) once US1 file REST lands

---

## Notes

- [P] = different files, no unfinished dependency, same wave only
- `routes/workspace.py`, `tools.py`, `schemas.py`, and `SkillManagementList.tsx` are
  shared across stories — do not put two edits of the same file in one [P] wave
- `ze_core` and `ze_agents` must not import `ze_workspace`; plugins must not either
- Do not implement wait-then-detach, automatic follow-up turns, or completion push (FR-024
  / spec 116)
- Do not fold `ze-browser` into the workspace (FR-022)
- Commit after each task or wave; stop at any checkpoint to validate the story
