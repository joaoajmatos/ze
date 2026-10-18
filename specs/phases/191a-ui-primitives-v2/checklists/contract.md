# Contract Requirements Checklist: UI Primitives v2 (191a)

**Purpose**: check the action, version and fallback requirements before implementation.
**Created**: 2026-10-18
**Feature**: [spec.md](../spec.md)

## Actions and gates

- [x] CHK001 Is every action kind specified with who handles it (browser or server)? [Completeness, Data model]
- [x] CHK002 Is it explicit that a tool action passes the veto, hooks and the asks-first gate? [Clarity, Spec §FR-002, Plan §ze-api]
- [x] CHK003 Is the owner check stated honestly (agent's opted-in write tools), with its refusal line? [Spec §FR-003, Contract, Gauge A-4]
- [x] CHK004 Are deny, timeout and busy outcomes worded? [Coverage, Contract]
- [x] CHK005 Is a double press defined? [Edge Case, Spec, T010]
- [x] CHK006 Is it stated that models can never set an action or posture? [Spec §FR-003a, Research R5, T007]

## Version and fallback

- [x] CHK007 Is the version carried on every transport that carries components, with T001 listing them? [Completeness, T001, T003]
- [x] CHK008 Are stored (unversioned) trees rendered as legacy, never failing the message? [Spec §FR-004, T008, T012]
- [x] CHK009 Is the fallback bounded (12 fields, nested children parsed, no raw objects)? [Edge Case, Spec, Data model]
- [x] CHK010 Do known malformed nodes still fail with a named path? [Spec US2-3, T008]

## Primitives and fixtures

- [x] CHK011 Does each slot need map to exactly one primitive? [Spec §FR-006, Research R4]
- [x] CHK012 Is the audit's removal rule stated and recorded before deletion? [T001, T002]
- [x] CHK013 Is a missing fixture a failing test on both sides? [Spec US4-2, T004, T009]
- [x] CHK014 Is the gallery excluded from production builds with a test? [Clarification Q3, T011]

## Lifecycle

- [x] CHK015 Are supersede, reconnect, restart, timeout and double-confirm defined for screen confirmations? [Spec §FR-012, T006]
- [x] CHK016 Is the outcome line sourced from declared phrases, never raw errors? [Spec §FR-013, Contract]
- [x] CHK017 Is the audit trail named (action ledger), with the trace claim removed? [Spec §FR-002, Plan]
- [x] CHK018 Can an asks-first write park outside the agent loop, with a real call id? [Plan §ze-agents, T005]
