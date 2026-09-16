# Research: Parallel Per-Subtask Gates

**Feature**: `158-parallel-subtask-gates`  
**Date**: 2026-09-16

## 1. Do not min() the envelope

**Decision:** `capability_check` for `is_compound` stores a per-subtask list of `GateDecision` (capability + spend budget composed as 152). Overall `gate_decision` is **BLOCKED** only when every subtask is BLOCKED; otherwise the graph still goes to `execute_tool` so EXECUTE/DRAFT jobs can run even if a sibling is AWAIT.

**Rejected:** Keep one `min()` and only split later. That is today’s bug. Sending mixed-decision compound to `draft_response` (current AWAIT/DRAFT edge) holds the whole turn.

## 2. execute_tool partitions; confirmations are 113

**Decision:** `_execute_compound` runs EXECUTE (and DRAFT-as-draft) immediately (`asyncio.gather` among those). AWAIT subtasks do not start `run`; each gets a pending confirmation keyed by `request_id`. On approve, only that specialist runs. Deny skips that write. Synthesize when no AWAIT remains pending (or after last terminal).

**Rejected:** One combined confirmation listing every held job. That reintroduces a single hold and confuses deny. Serializing EXECUTE behind the first AWAIT.

## 3. Conductor and 155 stay off this path

**Decision:** If the envelope is companion-primary / not compound fan-out, do not apply 158. `run_delegate` stays 152. Mixed gather+act that 155 rewrote never hits this code. A unit envelope that is still compound mixed is a safety net only.

**Rejected:** Teaching `_execute_compound` to feed prior outputs (sequential execute — deleted in 153).

## 4. Test hard-cut

**Decision:** Replace `test_compound_mixed_read_write_still_strictest_wins` with per-subtask assertions (SC-005). Add act+act both-AWAIT fixture.

**Rejected:** Leaving the old test as “documentation of 152’s out of scope.”
