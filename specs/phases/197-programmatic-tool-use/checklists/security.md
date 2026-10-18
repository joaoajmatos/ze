# Security Requirements Checklist: Programmatic Tool Use

**Purpose**: Test the quality of the requirements on sandboxing, gating and limits before build
**Created**: 2026-10-18
**Feature**: [spec.md](../spec.md) · Audience: reviewer (Gauge) · Depth: standard

## Isolation

- [x] CHK001 Is it required that the sandbox holds no Ze credential and opens no connection to Ze? [Completeness, Spec §FR-002, research R1]
- [x] CHK002 Is the script's network access specified (rejected), is the rule verified by reading it back (not by exit codes), is it re-probed per script, and is failing closed defined (including local dev without `NET_ADMIN`)? [Completeness, Spec §FR-005a, plan Sidecar, research R2; re-ticked after Gauge M-7]
- [x] CHK003 Is file access specified (scratch only, deleted after the run; `/workspace` closed at runtime because the volume mount masks the image's mode, and probed per script)? [Clarity, Spec §FR-005a, plan Sidecar; re-ticked after Gauge M-7]
- [x] CHK004 Is the boundary stated as the uid (not the import path), with `-I` kept for environment hygiene and the scratch dir put on `sys.path` explicitly? [Clarity, research R2; re-ticked after Gauge M-7]
- [x] CHK005 Are the environment, the resource limits (memory, processes, file size, CPU, open files, scratch size), stdout handling, line and frame size caps, and the uid-wide kill at the end all specified? [Completeness, Spec §FR-005a, FR-006, plan Sidecar, T019–T021; re-ticked after Gauge M-6]

## Gating

- [x] CHK006 Is every inner call required to go through the agent's normal tool path with gates, hooks, retry rules and caps unchanged? [Consistency, Spec §FR-004]
- [x] CHK007 Is the stub's tool set defined precisely, including what is excluded (writes, server tools, delegate, workspace, the script tool)? [Clarity, Spec §FR-003]
- [x] CHK008 Is a forged request for a tool outside the set required to be refused inside Ze, not only absent from the stub? [Coverage, Spec §FR-003, SC-003]
- [x] CHK009 Is the write path defined so no irreversible write runs without approval, including Retry and the round cap? [Coverage, Spec §FR-005, US3]
- [x] CHK010 Is reuse through procedures prevented from granting tools the agent no longer has? [Coverage, Spec §FR-010, US5 scenario 3]

## Limits

- [x] CHK011 Are wall time, inner calls, spend and result size quantified with defaults and named errors? [Measurability, Spec §FR-006, FR-007]
- [x] CHK012 Is the interaction with the per-turn tool-call cap defined? [Consistency, Spec §FR-006, US2 scenario 2]
- [x] CHK013 Is spend attribution defined (which model calls count toward a script, and that one call can overshoot)? [Clarity, research R5, Spec §FR-006]
- [x] CHK013a Is the interaction with the turn's tool-call cap defined so proposed writes are not starved by inner reads? [Consistency, Spec §FR-006; Gauge M-5]
- [x] CHK013b Are screen-drawing tools excluded from scripts by a declared flag, not a name prefix? [Clarity, Spec §FR-003; Gauge M-2]
- [x] CHK013c Is the script endpoint required to refuse when no token is configured? [Coverage, Spec §FR-005a; Gauge M-7]

## Data leaving Ze

- [x] CHK014 Is it stated why a script cannot send data to a third party: no network of its own, tools that reach a caller-chosen URL (`egress`, e.g. `browser_extract`) and server tools excluded from the stub, and a registry sweep that catches an unflagged URL-taking read tool? [Coverage, Spec §FR-003, research R7, ADR; re-ticked after Gauge R-1]

## Accountability

- [x] CHK015 Are the script source, outcome, limit and every inner call required on the trace? [Completeness, Spec §FR-008, SC-002]
- [x] CHK016 Is every script run required to leave an action record? [Completeness, plan Learning, T024]

## Notes

- All items pass against spec, plan and tasks as of 2026-10-18, after Gauge's review (M-1..M-7, Me-1..Me-5, N-1..N-7) and the user's answers on M-2 and Me-4.
