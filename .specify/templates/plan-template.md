# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]

**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]

**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]

**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]

**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]

**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]

**Project Type**: [e.g., library/cli/web-service/mobile-app/compiler/desktop-app or NEEDS CLARIFICATION]

**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]

**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]

**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source: `.specify/memory/constitution.md`. Assess every principle. PASS or
justified violation (Complexity Tracking).*

- **I. Spec-First Development**
- **II. Single-User Model**
- **III. Layered Package Architecture**
- **IV. Typed, Explicit Python**
- **V. Test Discipline**
- **VI. Explicit Persistence**
- **VII. One LLM Gateway, Local Embeddings**
- **VIII. Pre-v1 Hard Cuts** — breaking APIs/schemas is allowed until v1;
  compatibility shims, dual-write, and wrap-then-replace across phases are
  violations, not virtues. See `specs/arch/pre-v1-hard-cuts.md`.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Lane Plan (Maestri crew)

<!--
  REQUIRED. This plan is built by a crew working in parallel, not by one engineer in order.
  Split the work into lanes that own DISJOINT file sets, so lanes never edit the same file.
-->

**Contract step** (lane `lead`, lands first): [the shared types, component stubs, route slots,
schema fields and test fixtures every other lane builds against; list the files].

| Lane | Model / role | Owns (files and dirs, disjoint) | Tasks | Starts after | Reviewer |
|------|--------------|---------------------------------|-------|--------------|----------|
| lead | Sonnet ENG lead | shared files: router, places, query keys, app shell, generated client; integration | T001, T00x, ... | - | [name] |
| a | Sonnet ENG | [user story A's files] | ... | contract step | [name] |
| jr1 | Haiku JR | [pure, test-specified files] | ... | contract step | [name] |
| docs | Haiku DOCS | docs/, AGENTS.md rows, specs index | ... | each story's merge | [name] |

**Rules**: one lane per file; shared files belong to `lead` and other lanes request changes;
each lane works in its own git worktree on a sub-branch of the floor branch, and `lead` merges
the lane branches into the floor branch; each lane is reviewed as it finishes (small diffs);
JR lanes get only fully specified work (pure functions with the tests written into the task,
docs from a finished diff, codegen, captures, gate runs); design, cross-layer and integration
work stays on Sonnet or above. Size the crew to the phase: a small phase is `lead` alone.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
