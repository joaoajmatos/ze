# Implementation Plan: Workspace Chat-First

**Branch**: `161-workspace-chat-first` | **Date**: 2026-09-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/phases/161-workspace-chat-first/spec.md`

## Summary

Hard-cut workspace execution modes. `WorkspaceGate` decides from action × origin only: conversation confirms writes/commands/reset; unattended allows the same computer without a pause; the map (`/workspace`) lists the tree and occupancy. Drop `WorkspaceMode`, `PATCH /workspace/mode`, the mode column, and console controls on the System page and confirm bar. Keep isolation, busy/full, skill executable approval, wait-then-detach, and chat attachments.

## Project Structure

```text
specs/phases/161-workspace-chat-first/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/workspace-chat-first.md
└── tasks.md

core/ops/ze-workspace/ze_workspace/
├── types.py gate.py store.py tools.py rest.py procedure_candidates.py
└── migrations/versions/zws005_drop_workspace_mode.py

core/automation/ze-automation/ze_automation/
├── workspace_unattended.py  bootstrap.py  goals/executor.py

core/engine/ze-core/ze_core/
├── conversation/messages/types.py
└── orchestration/nodes/trace.py

apps/ze-api/ze_api/api/routes/workspace.py  schemas.py  container.py  openapi.py
apps/ze-web/src/widgets/workspace-management/
apps/ze-web/src/widgets/chat-workspace/ui/ChatWorkspace.tsx
apps/ze-web/src/widgets/trace-panel/ui/WorkspaceSection.tsx
apps/ze-web/src/entities/workspace/
packages/ze-client/src/generated/   # make codegen after schema cut
```

**Structure Decision**: Change the existing workspace package, automation duck-typed gate, API, and ze-web map — no new package.

## Constitution Check

| Principle | Assessment |
|-----------|------------|
| I. Spec-First | PASS — phase 161 spec before code |
| II. Single-User | PASS — still one workspace |
| III. Layered packages | PASS — gate stays in `ze-workspace`; automation stays duck-typed |
| IV. Typed Python | PASS — drop enum; dataclasses without mode |
| V. Test Discipline | PASS — rewrite gate/tools/unattended/web tests |
| VI. Explicit Persistence | PASS — `zws005` drops `workspace_state.mode` |
| VII. LLM / embeddings | PASS — untouched |
| VIII. Pre-v1 Hard Cuts | PASS — delete modes; no shim or dual-write |

Re-check after design: still PASS. `PLAN` gate decision dies with Plan mode.

## Technical Context

Existing stack: Python workspace package, FastAPI `/api/v0/workspace`, React `/workspace` page, `@ze/client` codegen.
