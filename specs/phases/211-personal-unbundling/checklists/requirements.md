# Specification Quality Checklist: ze-personal Unbundling

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-22
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- This is a package-placement refactor, so package and module names are the subject of the spec.
- Clarified 2026-10-22: contacts become the `plugins/ze-contacts` plugin, ze-messenger owns the channel stores and routes, and a data migration links contacts to person entities (FR-012).
- Re-checked against the code on 2026-10-22 (Sextant). Corrected line drift in nine references and the import counts (ze-api 12 plus 1 persona, messenger 14 in 5 files, prospecting 3 plus 1). Narrowed "only for contacts" (true for calendar; messenger also uses channels, prospecting also `OutreachLog`) and the import list (ze-news is a lazy import, ze-correlation arrives through `ze_sdk.correlation` and two undeclared direct imports). B14 is worse than reported: a completed goal can be paused and then resumed to `active` (the `pause_goal` undo is `resume_goal`), now Story 2 scenario 3. Added: FR-001 deletes the three ZePlugin hooks whose only adapter was ze-personal; FR-010 was unreachable as written (the companion and briefing stay in ze-personal and read `WorldComposer` and `PriorityView`), so it now forbids importing automation internals rather than the dependency itself; an edge case on moving the contacts and channel migrations out of the shared `zc` chain.
