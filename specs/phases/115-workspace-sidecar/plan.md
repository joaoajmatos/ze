# Implementation Plan: Workspace Environment

**Branch**: `115-workspace-sidecar` | **Date**: 2026-08-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/phases/115-workspace-sidecar/spec.md`

## Summary

Give Ze a single durable, isolated computer on the always-on side — files, a shell, and
ordinary scripting runtimes — without moving the mind or touching the user's laptop. A new
`core/ze-workspace` package plus `sidecar/workspace` follow the browser-helper split: Ze
calls a control API; programs run in a stripped, unprivileged subprocess that can reach the
public internet but not Ze's private services or credentials. Conversational runs complete
inside the turn. Workspace modes (Off / Plan / Ask / Auto-edit / Auto) persist as a
singleton and reuse `pending_confirmations` via in-node `interrupt()`, rather than a
parallel auth system. Phase 114's discarded skill scripts are stored and require a separate
executable approval before `workspace_run_skill_script` may run them. Detach, follow-up
turns, and completion push stay out of this spec.

## Technical Context

**Language/Version**: Python 3.11+ (backend / sidecar), TypeScript/React (ze-web) — matches
existing stack.

**Primary Dependencies**: `ze-agents`, `ze-logging`, `ze-data`, `httpx`, `asyncpg` (new
`ze-workspace` core package); sidecar is a small FastAPI/uvicorn service like
`sidecar/browser` (no Ze package imports). Ingest reuses `IngestionPipeline` via DI
(`file_bytes` path) — no `ze-ingestion` package dependency. Extends `ze-skills`
importer/review (`zsk002`). LangGraph 1.2.2 `interrupt()` + existing
`pending_confirmations` for Ask-mode confirms. Confirmation error type lives in
`ze-agents`. No new LLM provider; no new embedding model.

**Storage**: PostgreSQL via asyncpg — `workspace_state`, `workspace_runs` (`zws001`);
`skill_scripts` + `skills.has_scripts` / `executable_approved` (`zsk002`). Durable files
live on a Compose volume / Fly volume at `/workspace`, not in Postgres. Run records in
Postgres are the attach point for a later follow-through spec.

**Testing**: pytest (`core/ze-workspace/tests/`, `sidecar/workspace` logic tested via the
client with a fake HTTP sidecar; `ze-skills` importer/review tests updated; `ze-api` REST
tests; vitest for workspace page + ConfirmBar edit + message chip). No real Docker, Fly,
or network in unit tests. Mock asyncpg and `WorkspaceClient`.

**Target Platform**: Existing FastAPI service + React SPA, plus one new always-on sidecar
(Compose locally, Fly app + volume in prod).

**Project Type**: Web application + sidecar (existing monorepo layout).

**Performance Goals**: SC-001 (create + retrieve a named file, including confirm, under 2
minutes); SC-006 (find/retrieve or reset from the workspace view under 30 seconds); SC-008
(mode switch Ask → Auto-edit takes effect on the next write under 30 seconds). Control-API
health checks in the same order as the browser sidecar.

**Constraints**: No Ze credentials or internal service locations in the workspace or in
user-visible run output (SC-004, FR-003). No GUI computer-use, no local-machine access, no
folding `ze-browser` into the workspace (FR-022, FR-023). No detach / auto follow-up / push
(FR-024). Instructions-only skill approvals must not start running scripts (SC-005,
FR-012). One run at a time (FR-019). Storage ceiling enforced (FR-020).

**Scale/Scope**: Single-user, one workspace. Conservative defaults: 120s run budget, 8k
inline preview, 1 GiB ceiling. Management UI is one System page plus chat chips / confirms.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First Development** — PASS. This plan follows
  `specs/phases/115-workspace-sidecar/spec.md`.
- **II. Single-User Model** — PASS. One workspace, no `user_id` / tenancy; `workspace_state`
  is a singleton row; REST gated by the existing API key.
- **III. Layered Package Architecture** — PASS. `ze-workspace` is a `core/` package with no
  plugin-domain knowledge; sidecar has no Ze imports (same as `sidecar/browser`). Wired by
  `apps/ze-api`. `ze_core` and `ze_agents` do not import `ze_workspace`. Confirmation uses
  `ToolConfirmationRequired` in `ze_agents.errors` (tools raise it; `call_tool` /
  `execute_tool` catch it). `WorkspaceGate` / `WorkspaceClient` are injected via
  `config["configurable"]` and constructor `deps`. Unattended gating lives in
  `ze-automation` executors with the same injection — plugins (`ze_personal` included)
  do not import `ze_workspace`. `IngestionPipeline` is injected into
  `ingest_workspace_file`; `ze-workspace` does not depend on `ze-ingestion`. Skill
  executable approval stays in `ze-skills`. Platform tools register through `@tool` +
  `BaseAgent` name merge.
- **IV. Typed, Explicit Python** — PASS. Dataclasses in `types.py`, `StrEnum` for mode /
  run status / origin, typed `ZeError` subclasses, async I/O, constructor injection.
- **V. Test Discipline** — PASS (planned). Tests in `core/ze-workspace/tests/`,
  `core/ze-skills/tests/` (importer stores scripts; approve-executables), `apps/ze-api/tests/`,
  `apps/ze-web/src/**/*.test.ts(x)`. Fake sidecar HTTP, mock pools, no real LLM.
- **VI. Explicit Persistence** — PASS. Raw-SQL Alembic `zws001` in `ze-workspace`, `zsk002`
  in `ze-skills`. No ORM. Meta-runner constant `_ZE_WORKSPACE_VERSIONS`.
- **VII. One LLM Gateway, Local Embeddings** — PASS. No new LLM or embedding path. Workspace
  execution is subprocesses, not model calls.

No violations requiring Complexity Tracking justification.

**Post-Phase-1 re-check** (updated after analyze remediations): `ToolConfirmationRequired`
lives in `ze-agents`, ingest is injected, unattended gating stays in `ze-automation`,
output sanitizer covers SC-004. Still no per-user columns, no ORM, no core enum of plugin
identities. Gate still PASSES after design.

## Project Structure

### Documentation (this feature)

```text
specs/phases/115-workspace-sidecar/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md         # Phase 1
├── quickstart.md         # Phase 1
├── contracts/
│   ├── workspace-api.md           # REST + WS/trace + confirm edit
│   └── workspace-sidecar.md       # Internal control API
└── tasks.md              # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
sidecar/workspace/                         # NEW — the computer (no Ze imports)
├── Dockerfile
├── fly.toml                               # app ze-workspace, volume, min_machines_running=1
├── requirements.txt
├── main.py                                # FastAPI: /health, /stat, /fs*, /run, /reset, /cancel
├── supervisor.py                          # unprivileged exec, mutex, timeout, nftables
└── README.md

core/ze-workspace/                         # NEW core package
├── pyproject.toml
└── ze_workspace/
    ├── __init__.py
    ├── types.py                           # WorkspaceMode, WorkspaceRun, WorkspaceFile, …
    ├── errors.py                          # WorkspaceUnavailableError, WorkspaceBusyError,
    │                                      # WorkspaceFullError, WorkspacePathError, …
    │                                      # (no confirm-interrupt type — that lives in ze-agents)
    ├── sanitize.py                        # denylist redact of previews/errors (SC-004)
    ├── client.py                          # WorkspaceClient (httpx → sidecar)
    ├── store.py                           # WorkspaceStore + PostgresWorkspaceStore
    ├── gate.py                            # WorkspaceGate (mode × action × origin)
    ├── tools.py                           # @tool workspace_* + ingest_workspace_file
    │                                      #   (raises ToolConfirmationRequired; ingest via deps)
    ├── rest.py                            # thin dict facade for REST
    ├── bootstrap.py                       # build_workspace_stack(shared, settings)
    └── migrations/
        ├── env.py
        └── versions/
            └── zws001_workspace.py        # workspace_state, workspace_runs

core/ze-skills/ze_skills/
├── types.py                               # + has_scripts, executable_approved; skill_scripts
├── parser.py / importer.py                # persist scripts instead of discarding
├── review.py                              # approve_skill_executables()
├── rest.py / store.py
└── migrations/versions/zsk002_skill_scripts.py

core/ze-agents/ze_agents/errors.py         # ToolConfirmationRequired (next to ToolBlockedError)
core/ze-agents/ze_agents/base_agent.py     # merge WORKSPACE_TOOLS; catch ToolConfirmationRequired
core/ze-core/ze_core/orchestration/nodes/execution.py  # interrupt() on ToolConfirmationRequired
core/ze-core/ze_core/conversation/turn.py  # Command(resume=) for workspace confirms
core/ze-core/ze_core/conversation/messages/types.py    # MessageTrace.workspace, SkillUsageTrace.script_ran
core/ze-core/ze_core/orchestration/nodes/trace.py      # populate workspace usage
core/ze-automation/ze_automation/goals/executor.py      # injected WorkspaceGate, origin=unattended
core/ze-automation/ze_automation/workflow/              # same; not ze_personal.graph.workflow

apps/ze-api/ze_api/container.py            # WorkspaceClient + stack, configurable injection
apps/ze-api/ze_api/settings.py             # WORKSPACE_SERVICE_URL, token, timeout
apps/ze-api/ze_api/migrate.py              # _ZE_WORKSPACE_VERSIONS
apps/ze-api/ze_api/api/routes/workspace.py
apps/ze-api/ze_api/api/routes/skills.py    # POST …/approve-executables
apps/ze-api/ze_api/api/schemas.py          # Workspace* + confirm edited_content
apps/ze-api/ze_api/api/websocket/…         # confirm edit; message context.workspace_placed
apps/ze-api/config/config.yaml             # workspace: block
apps/ze-api/.env.example                   # WORKSPACE_* 
apps/ze-api/pyproject.toml                 # dep ze-workspace
docker-compose.yml                         # workspace service + volume
Makefile / docs/testing.md                 # test-workspace

apps/ze-web/src/entities/workspace/
apps/ze-web/src/widgets/workspace-management/
apps/ze-web/src/pages/workspace/
apps/ze-web/src/shared/config/nav-routes.ts          # systemNavRoutes + "workspace"
apps/ze-web/src/entities/message/ui/ChatInput.tsx    # attach → REST place
apps/ze-web/src/entities/message/ui/MessageBubble.tsx # workspace file chip
apps/ze-web/src/entities/message/ui/ConfirmBar.tsx    # editable content
apps/ze-web/src/widgets/trace-panel/ui/WorkspaceSection.tsx
apps/ze-web/src/widgets/skill-management/…            # scripts + executable approval

core/ze-workspace/tests/
core/ze-skills/tests/                      # importer stores scripts; no silent promotion
apps/ze-api/tests/
apps/ze-web/src/**/*.test.ts(x)
```

**Structure Decision**: New `core/ze-workspace/` (directly wired, like `ze-skills`) plus
`sidecar/workspace/` (like `sidecar/browser`). Confirmation extends the existing graph
resume path rather than adding a node, using `ToolConfirmationRequired` in `ze-agents`
so the engine never imports `ze-workspace`. Skill-script persistence stays in `ze-skills`
because that package already owns `SKILL.md` parsing. Frontend copies the Skills System-page
pattern (`entities/` + `widgets/` + thin `pages/`).
