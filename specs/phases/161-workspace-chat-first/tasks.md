# Tasks: Workspace Chat-First

**Input**: [spec.md](./spec.md), [plan.md](./plan.md)

## Phase 1: Setup

**Wave 1 — independent:**

- [x] **T001** [P] Point `.specify/feature.json` at `specs/phases/161-workspace-chat-first` (already done if specify ran)

## Phase 2: Foundational

**Wave 1 — independent (different files):**

- [x] **T002** [P] Remove `WorkspaceMode` and `WorkspaceGateDecision.PLAN`; drop `mode` from `WorkspaceState` · `core/ops/ze-workspace/ze_workspace/types.py`
- [x] **T003** [P] Add `zws005` dropping `workspace_state.mode` · `core/ops/ze-workspace/ze_workspace/migrations/versions/zws005_drop_workspace_mode.py`

**⟶ Wait for Wave 1 to finish, then:**

- [x] **T004** Rewrite `WorkspaceGate.decide` / `decide_named` as action × origin (no mode) · `core/ops/ze-workspace/ze_workspace/gate.py`
- [x] **T005** Rewrite `test_gate.py` for the new table · `core/ops/ze-workspace/tests/test_gate.py`

**⟶ Wait for Wave 2 to finish, then:**

- [x] **T006** Remove `get_mode`/`set_mode`; stop reading `mode` in `get_state` · `core/ops/ze-workspace/ze_workspace/store.py`
- [x] **T007** Rewrite store mode tests · `core/ops/ze-workspace/tests/test_store.py`

## Phase 3: User Story 1 — Chat computer (P1)

**Independent Test**: Conversation write/run confirm then execute; no Off/Plan refuse.

- [x] **T008** [US1] Tools: `_decide` without mode; confirm copy without mode; drop PLAN/DENY-by-mode paths · `core/ops/ze-workspace/ze_workspace/tools.py`
- [x] **T009** [US1] Rewrite `test_tools.py` (conversation confirm; unattended allow) · `core/ops/ze-workspace/tests/test_tools.py`

## Phase 4: User Story 2 — Unattended always on (P1)

- [x] **T010** [US2] `consult_unattended` / `unattended_workspace(gate)` without mode · `core/automation/ze-automation/ze_automation/workspace_unattended.py`
- [x] **T011** [US2] Stop passing `get_workspace_mode` · `core/automation/ze-automation/ze_automation/goals/executor.py`, `core/automation/ze-automation/ze_automation/bootstrap.py`, `apps/ze-api/ze_api/container.py`
- [x] **T012** [US2] Rewrite `test_workspace_unattended.py` · `core/automation/ze-automation/tests/test_workspace_unattended.py`
- [x] **T013** [P] [US2] Procedure candidates without mode · `core/ops/ze-workspace/ze_workspace/procedure_candidates.py`, `core/ops/ze-workspace/tests/test_procedure_candidates.py`

## Phase 5: User Story 3 — Map-only `/workspace` (P1)

- [x] **T014** [US3] Strip mode/upload/reset/runs/retrieve from the page · `apps/ze-web/src/widgets/workspace-management/ui/WorkspaceManagement.tsx`
- [x] **T015** [US3] Delete mode switcher and stop exporting it; drop confirm-bar switcher · `apps/ze-web/src/widgets/workspace-management/ui/WorkspaceModeSwitcher.tsx`, `index.ts`, `ChatWorkspace.tsx`, `ConfirmBar.tsx`
- [x] **T016** [US3] Drop `mode` from entity types; delete `useWorkspaceModeMutation` · `apps/ze-web/src/entities/workspace/`
- [x] **T017** [US3] Rewrite `WorkspaceManagement.test.tsx` for map-only · `apps/ze-web/src/widgets/workspace-management/ui/WorkspaceManagement.test.tsx`

## Phase 6: User Story 4 — Modes gone from API and living copy (P2)

- [x] **T018** [US4] Remove mode routes and `mode` from status/trace schemas · `apps/ze-api/ze_api/api/routes/workspace.py`, `ze_workspace/rest.py`, `ze_api/api/schemas.py`, `openapi.py`
- [x] **T019** [US4] Drop `mode` from `WorkspaceUsageTrace` and trace node · `core/engine/ze-core/ze_core/conversation/messages/types.py`, `orchestration/nodes/trace.py`
- [x] **T020** [US4] Trace panel and message bubble without mode · `apps/ze-web/src/widgets/trace-panel/ui/WorkspaceSection.tsx`, `MessageBubble.tsx` and tests
- [x] **T021** [US4] API tests without `/workspace/mode` · `apps/ze-api/tests/api/routes/test_workspace.py` and followthrough mocks
- [x] **T022** [US4] `make codegen` · `packages/ze-client/src/generated/`
- [x] **T023** [US4] Living docs: AGENTS/CLAUDE phase 115/161, `specs/README.md`, workspace README, constitution index if it names modes · `AGENTS.md`, `CLAUDE.md`, `core/ops/ze-workspace/README.md`

## Phase 7: Polish

- [x] **T024** Mark spec Implemented; README row Implemented · `specs/phases/161-workspace-chat-first/spec.md`, `specs/README.md`
- [x] **T025** Validate: `make test-workspace`, `make test-automation`, `make test-core` (trace), `make test`, `make test-web`, `make lint`

## Dependencies & Execution Order

Setup → Foundational (types/migration then gate then store) → US1 tools → US2 unattended → US3 map → US4 API/docs → Polish suites.

FR map: FR-001 T008–T009; FR-002/FR-009 T002–T007 T018 T022; FR-003 T008; FR-004 T010–T012; FR-005/FR-007 T014–T017; FR-006 T004 T008; FR-008 T014 T020; FR-010 keep; FR-011 T023; FR-012 existing unavailable paths in tools.
