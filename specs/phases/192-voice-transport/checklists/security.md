# Security and Failure-Path Requirements Checklist: Voice Input Transport (B3)

**Purpose**: Unit tests for the requirements (not the code) on upload handling, untrusted client input, the no-storage rule and failure paths. Audience: PR reviewer (Gauge), before implementation.
**Created**: 2026-10-18
**Feature**: [spec.md](../spec.md) · [plan.md](../plan.md) · [contract](../contracts/transcribe-voice.md)

## Requirement Completeness

- [x] CHK001 Are accepted media types listed exhaustively, including codec-parameter variants? [Completeness, Spec §FR-001, Contract]
- [x] CHK002 Are both upload caps (size and length) stated with exact limits? [Completeness, Spec §FR-001]
- [x] CHK003 Is authentication specified for the new route, the same as for other REST routes? [Completeness, Spec Edge Cases]
- [x] CHK004 Is a distinct, plain error defined for every rejection class (type, size, length, unreadable, model failure, tools missing)? [Completeness, Spec §FR-002, Contract]
- [x] CHK005 Is it stated that nothing is stored on failure? [Completeness, Spec US2 scenario 3]

## Requirement Clarity

- [x] CHK006 Is "not stored" defined precisely: audio never persisted, the transcript only in memory for 10 minutes, and never on the trace? [Clarity, Spec §FR-004, Clarifications Q2]
- [x] CHK007 Is the source of the length measurement unambiguous (the server, never the client)? [Clarity, Spec Assumptions, Clarifications Q3]
- [x] CHK008 Is "edited" defined by a server-side comparison rule rather than a client flag? [Clarity, Research R5, Contract]
- [ ] CHK009 Does the spec say whether the size cap is enforced while streaming (no full buffering of oversized bodies)? [Clarity, Gap: in plan Constraints and T012 only]

## Untrusted Input

- [x] CHK010 Is the behaviour for an unknown, expired or malformed transcription reference specified (text turn, no trust)? [Coverage, Spec US1 scenario 3]
- [x] CHK011 Is a maximum length set for the reference string accepted in the message context? [Coverage, Contract, plan `WsVoiceRef` max 64]
- [x] CHK012 Is the client-declared content type treated as a claim, with the server's probe deciding readability? [Consistency, Spec §FR-002, Research R1]

## Failure and Recovery

- [x] CHK013 Is the recovery path after a failed transcription defined (retry with the same recording, no re-record)? [Recovery, Spec US2; client side in 193]
- [x] CHK014 Is behaviour after a server restart defined for live references? [Recovery, Spec Edge Cases]
- [x] CHK015 Is the missing-ffmpeg deployment case specified with a user-facing line and an operator log? [Exception Flow, Spec §FR-002, Plan]

## Dependencies and Assumptions

- [x] CHK016 Is the new runtime dependency (audio tools in the server image) recorded with its reason? [Dependency, Spec Assumptions, Plan Complexity Tracking]
- [x] CHK017 Is the single-instance assumption behind the in-memory registry stated? [Assumption, Spec Assumptions]

## Notes

- CHK009 is satisfied in plan and tasks (chunked read, abort past the cap, T012 asserts it) but not stated in the spec; acceptable at spec level (it is an implementation guard), recorded for the reviewer.
