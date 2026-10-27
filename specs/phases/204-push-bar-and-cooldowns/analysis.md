# Analysis: Push Bar and Cooldowns

**Run**: `/speckit-analyze`, 2026-10-26, on `spec.md`, `plan.md`, `tasks.md` at `a0fb461c`.

## Findings (all fixed in the same commit as this file)

| ID | Category | Severity | Location | Finding | Fix |
|----|----------|----------|----------|---------|-----|
| F1 | Inconsistency | MEDIUM | spec US1 AS1; T012–T014 | AS1 expected outcome `deduped`, but the job's pre-check (R9) returns before `notify` | AS1 reworded: the job skips on its cooldown; a racing run gets `deduped` |
| U1 | Underspecification | MEDIUM | T006 | The pg harness is always at head, so "seed old rows, then run the migration" could not run there | Upgrade check moved to T041 on a scratch DB first migrated by main; T007 exposes `DELETE_NON_CLAIMS_SQL` |
| U2 | Underspecification | MEDIUM | T028, T033, pg `conftest.py` | Workflow tables and the new `surfacing_memory` are not truncated by the harness until T038 | Lane pg tests isolate by fresh UUIDs; T038 adds the three tables to `RESET_TABLES` |
| E1 | Coverage gap | MEDIUM | SC-005 | No test showed a new source kind needs no bar or job change | T021 screens an unseen `source_kind`; T025 runs three fake sources of three kinds through one path |
| E2 | Coverage gap | LOW | Edge case "two targets never block each other" | Implied only | Stated in T006 |
| I1 | Inconsistency | LOW | T037 | The register function's new parameters were not named | T037 names `push_bar` and `push_sources` |

## Coverage

FR-001–FR-016: every requirement has at least one task. SC-001 T040; SC-002 T009, T011; SC-003 T025; SC-004 T029; SC-005 T021, T025; SC-006 T031.

## Constitution

No conflict. Plan's Constitution Check passes all eight principles.

## Metrics

16 functional requirements, 6 success criteria, 45 tasks, 100% requirement coverage, 0 ambiguities, 0 duplicates, 0 critical issues.
