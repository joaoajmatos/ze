# API Requirements Checklist: Accountability Surfaces (B4)

**Purpose**: Unit tests for the requirements (not the code) of the five read surfaces and the reset deletion. Audience: PR reviewer (Gauge).
**Created**: 2026-10-18
**Feature**: [spec.md](../spec.md) · [contracts/rest.md](../contracts/rest.md)

## Completeness

- [x] CHK001 Are filters, paging and ordering specified for the action list? [Completeness, Spec §FR-001, Contract]
- [x] CHK002 Is the empty-result behaviour specified for every list surface? [Completeness, Spec US1 scenario 4, Edge Cases]
- [x] CHK003 Are all channel states, including push channels, specified? [Completeness, Spec §FR-008, US5]
- [x] CHK004 Is the fate of each logged gap recorded (here or which follow-up)? [Completeness, Spec "Logged gaps and where they went"]

## Clarity and Consistency

- [x] CHK005 Is the subject → context mapping closed and named? [Clarity, Research R1, Data Model]
- [x] CHK006 Is "last change" for loops defined by a stored field? [Clarity, Research R4]
- [x] CHK007 Does the tier route name its single configuration source? [Consistency, Spec §FR-004, Research R6]
- [x] CHK008 Are request-validation failures (lone subject param, bad cursor, limit out of range) specified with status codes? [Clarity, Contract]

## Security and Privacy

- [x] CHK009 Is "no secrets in responses" stated for the tier and channel routes? [Security, Spec US3 scenario 3, US5 scenario 5]
- [x] CHK010 Is auth required on every new route? [Security, Contract]
- [x] CHK011 Is user input kept out of SQL identifiers (subject keys from a closed map)? [Security, Plan Design]

## Recovery and Edge Cases

- [x] CHK012 Is a stable order defined for same-timestamp records under paging? [Edge Case, Spec Edge Cases, Research R3]
- [x] CHK013 Is the developer path after the reset deletion stated? [Recovery, Spec US6]
- [x] CHK014 Is the migration's downgrade defined? [Recovery, Data Model]
