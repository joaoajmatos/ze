# Specification Quality Checklist: Data Domain Factory

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

- This is an internal refactor with a user-facing privacy fix, so table, package and route names are the subject of the spec. The spec says what each owner declares and what the delete, export and import must guarantee; how the factory and the foreign-key ordering are built is left to the plan.
- Audit claims corrected against the code: the factory is copied nine times, not six (worldstate, feedback records and proactive were missed; finance hand-writes every function and has no importer). B13 holds for `goals` and `workflows` only; memory tables are not exported twice, though ze-personal declares them without owning them. The audit missed the larger gap: 45 live tables are in no domain.
- Clarified 2026-10-22: full coverage, one row per area counted by its main table, and a failed export fails whole.
