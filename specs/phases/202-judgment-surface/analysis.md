# Analysis: Judgment Surface

`/speckit-analyze` over spec.md, plan.md and tasks.md, 2026-10-26, after `6bc44813`. Findings marked fixed were corrected in the same commit as this file.

## Findings

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| F1 | Inconsistency | MEDIUM | quickstart.md §2–§3; contracts/calibration-harness.md (Golden checks, SC-004 check); contracts/judgment-surface.md (intro) | Task IDs written before tasks.md was numbered (T020, T003, T006, T030, T041) | Fixed: T009, T002, T004, T025, T037, T002–T007 |
| U1 | Underspecification | MEDIUM | tasks.md T009 | The fake intake result was "IntakeOutcome-like"; ze-core cannot import `IntakeOutcome` (ze-worldstate) | Fixed: a `SimpleNamespace` with `kind`, `reason`, `link_kind`, and an empty `FactAdmission(path="haiku")` |
| C1 | Coverage | LOW | spec.md FR-009 | No 202 task; FR-009 is delivered by 203 (Clarifications 2026-10-26) | Accepted: T042 hands 203 the final shapes; 203's plan carries the task |
| A1 | Ambiguity | LOW | spec.md FR-007 | `uncalibrated` is listed as a decision reason, but `gate()` stops an uncalibrated surface before `decide()` runs, so a record never carries it | Accepted: the example is still a valid decision reason (`decide()` returns it if called); no behaviour depends on it |
| A2 | Ambiguity | LOW | contracts/calibration-harness.md `load_jsonl` | "raises on duplicate id" names no error type | Accepted: `eval/calibration` is a script directory outside domain code (AGENTS.md's `ZeError` rule covers domain code); the lane may report duplicates as a shape problem instead |
| R1 | Risk | LOW | tasks.md T006 | Whether `JsonPlusSerializer` round-trips a frozen dataclass holding a `frozenset` and nested dataclasses is assumed, not checked | Covered: T006's round-trip test fails early if it does not, and the lane fixes the record shape before any other lane builds on it |

No CRITICAL or HIGH finding. No duplication.

## Coverage

| Requirement | Has task? | Task IDs | Notes |
|---|---|---|---|
| FR-001 | yes | T002, T003 | |
| FR-002 | yes | T010, T012, T013, T015, T016, T021 | decide() untouched |
| FR-003 | yes | T002, T003 | |
| FR-004 | yes | T011, T012, T013, T016, T017, T018 | |
| FR-005 | yes | T014, T019, T020 | |
| FR-006 | yes | T008, T009, T017 | |
| FR-007 | yes | T002, T009, T016 | |
| FR-008 | yes | T012 | |
| FR-009 | 203 | (T042 handoff) | Clarifications 2026-10-26 |
| FR-010 | yes | T027 | |
| FR-011 | yes | T028–T034, T036 | |
| FR-012 | yes | T040 | §6 diff review |
| SC-001 | yes | T008, T009 | |
| SC-002 | yes | T002, T004, T019 | |
| SC-003 | yes | T039 | |
| SC-004 | yes | T036, T037 | |
| SC-005 | yes | T040 | |
| SC-006 | yes | T002, T008, T009, T012 | |

**Unmapped tasks**: none (T001, T007, T022, T023, T038, T041 are gates; T043–T046 docs).

## Constitution alignment

All eight principles pass (plan.md Constitution Check). The one deviation, process-level warn-once state through `functools.lru_cache`, is justified in plan.md Complexity Tracking.

## Metrics

- Requirements: 12 FR + 6 SC = 18
- Tasks: 46
- Coverage: 17 of 18 with a 202 task (FR-009 delivered by 203)
- Ambiguities: 2 (LOW)
- Duplications: 0
- Critical issues: 0
