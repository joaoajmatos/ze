# Security Requirements Checklist: Programmatic Tool Use

**Purpose**: Test the quality of the requirements on sandboxing, gating and limits before build
**Created**: 2026-10-18
**Feature**: [spec.md](../spec.md) · Audience: reviewer (Gauge) · Depth: standard

## Isolation

- [x] CHK001 Is it required that the sandbox holds no Ze credential and opens no connection to Ze? [Completeness, Spec §FR-002, research R1]
- [x] CHK002 Is the script's network access specified (none) and is failing closed defined when isolation cannot be applied? [Completeness, Spec §FR-005a, plan Sidecar, research R2]
- [x] CHK003 Is file access specified (scratch only, `/workspace` unreadable, scratch deleted after the run)? [Clarity, Spec §FR-005a, data-model]
- [x] CHK004 Is the import path specified so a script cannot shadow the stub or stdlib? [Edge Case, research R2]
- [x] CHK005 Is the environment passed to the script enumerated? [Completeness, plan Sidecar, T020]

## Gating

- [x] CHK006 Is every inner call required to go through the agent's normal tool path with gates, hooks, retry rules and caps unchanged? [Consistency, Spec §FR-004]
- [x] CHK007 Is the stub's tool set defined precisely, including what is excluded (writes, server tools, delegate, workspace, the script tool)? [Clarity, Spec §FR-003]
- [x] CHK008 Is a forged request for a tool outside the set required to be refused inside Ze, not only absent from the stub? [Coverage, Spec §FR-003, SC-003]
- [x] CHK009 Is the write path defined so no irreversible write runs without approval, including Retry and the round cap? [Coverage, Spec §FR-005, US3]
- [x] CHK010 Is reuse through procedures prevented from granting tools the agent no longer has? [Coverage, Spec §FR-010, US5 scenario 3]

## Limits

- [x] CHK011 Are wall time, inner calls, spend and result size quantified with defaults and named errors? [Measurability, Spec §FR-006, FR-007]
- [x] CHK012 Is the interaction with the per-turn tool-call cap defined? [Consistency, Spec §FR-006, US2 scenario 2]
- [x] CHK013 Is spend attribution defined (which model calls count toward a script)? [Clarity, research R5]

## Data leaving Ze

- [x] CHK014 Is it stated why a script cannot send data to a third party (no network; read tools of opted-in agents do not call out; server tools excluded) and that a future outbound read tool must be reviewed against it? [Assumption, research R7, ADR]

## Accountability

- [x] CHK015 Are the script source, outcome, limit and every inner call required on the trace? [Completeness, Spec §FR-008, SC-002]
- [x] CHK016 Is every script run required to leave an action record? [Completeness, plan Learning, T024]

## Notes

- All items pass against spec, plan and tasks as of 2026-10-18.
