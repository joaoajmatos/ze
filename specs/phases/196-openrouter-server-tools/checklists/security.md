# Security Requirements Checklist: OpenRouter Server Tools

**Purpose**: Test the quality of the requirements on outside tools, untrusted content and spend visibility before build
**Created**: 2026-10-18
**Feature**: [spec.md](../spec.md) · Audience: reviewer (Gauge) · Depth: standard

## Requirement Completeness

- [x] CHK001 Is the full set of server tools Ze may send defined as one closed list? [Completeness, Spec §FR-001]
- [x] CHK002 Is the failure mode for a declared non-allowlisted server tool specified (startup, error content)? [Completeness, Spec §FR-002]
- [x] CHK003 Is behavior defined for a server tool OpenRouter returns that Ze never sent? [Coverage, Spec §FR-005, US2 scenario 3]
- [x] CHK004 Are all code paths that could reach OpenRouter's web features without a declared tool identified and removed (the `:online` suffix)? [Completeness, Spec §FR-006]
- [x] CHK005 Is the fetch engine, and therefore which third party sees fetched URLs, stated and configurable? [Completeness, Clarifications Q1, Spec §FR-004]

## Untrusted content

- [x] CHK006 Do the requirements state that fetched and searched text is data, never instructions? [Clarity, Spec §FR-003]
- [x] CHK007 Is it explicit that a write prompted by page content still goes through the 181 gate? [Consistency, US1 scenario 3]
- [x] CHK008 Is the reach of a fetch (OpenRouter's side, cannot reach the user's network) stated? [Assumption, Edge Cases]
- [x] CHK008a Is the exfiltration case (a page makes the model put private memory into a fetch URL or search query) addressed by a recorded decision? [Coverage, Spec Clarifications 2026-10-18: user chose open fetch and accepted the risk; mitigations: cap, instructions, targets on the trace (FR-007a)]
- [x] CHK008d Can the user see what left (every fetch target and search query Ze can see), and is the case where OpenRouter exposes none stated? [Coverage, Spec §FR-007a, FR-009, T025]
- [x] CHK008b Is the residual leak through search queries recorded as a known limit? [Gap → ADR amendment, research R6]
- [x] CHK008c Is there a last-mile guard so a future caller of the OpenRouter client cannot send a non-allowlisted server tool? [Coverage, Spec §FR-005a]

## Spend and observability

- [x] CHK009 Is it defined where paid-engine fees appear (generation cost backfill) so no second price table is needed? [Clarity, Assumptions]
- [x] CHK010 Is the trace behavior for "no count reported" distinguished from "zero"? [Clarity, US3 scenario 2]
- [x] CHK011 Are per-request limits (fetch cap, content cap) quantified with defaults? [Measurability, Assumptions, data-model]

## Edge cases and recovery

- [x] CHK012 Are the OpenRouter 403 cases (workspace locked mode, regional endpoints) covered with a defined user-visible outcome? [Coverage, Edge Cases]
- [x] CHK013 Is truncated-page behavior defined for the agent's answer? [Edge Case, Spec Edge Cases]
- [x] CHK014 Is a malformed `server_tool_use` value handled without failing the turn? [Coverage, plan Constraints, T013]

## Notes

- All items pass against spec, plan and tasks as of 2026-10-18 (after Gauge review S-1 to S-11). The user chose open fetch on 2026-10-18 and accepted the URL-exfiltration risk; CHK008a records that decision rather than a control.
