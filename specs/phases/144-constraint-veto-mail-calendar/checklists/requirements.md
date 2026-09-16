# Specification Quality Checklist: Constraint Veto on Gated Writes

**Purpose**: Validate Companion specification completeness before planning
**Created**: 2026-09-16
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed (User Scenarios, Requirements, Success Criteria)

## Requirement Completeness

- [x] Any [NEEDS CLARIFICATION] markers are genuine ambiguities (≤3) deferred to clarify — not unresolved guesses
- [x] Each Functional Requirement is a single, testable MUST/SHOULD statement
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
- [x] No implementation details leak into the specification

## Notes

- Scope pin: shared opt-in `constraint_gate` on writes; not a core list of mail/calendar names. First required adopters: mail send, calendar mutations, reminders, prospecting outreach.
- Verbatim Constraints pin `constraint_gate` plus first-adopter tool names and `constraint` / `remember_fact` / `ok`. Allowed exception.
- Content Quality “no APIs” is pass: success criteria speak of writes completing and user-visible claims; identifiers live in FRs and Verbatim Constraints.
- Zero `[NEEDS CLARIFICATION]` — opt-in default, draft vs send, timezone, and ambiguous match are informed defaults under Assumptions.
- Size: oversized (guardrail) — shared gate plus several in-tree adopters; full pipeline. Plan/tasks/implement not run.
