# Quickstart: 158 Parallel Per-Subtask Gates

1. Fail-first: replace `test_compound_mixed_read_write_still_strictest_wins` so EXECUTE sibling is not held.
2. `capability_check` writes `subtask_gate_decisions`; compound does not `min()` to one AWAIT.
3. `_execute_compound` partitions EXECUTE/DRAFT vs AWAIT vs BLOCKED; 113 `request_id` per AWAIT.
4. Resume runs only the approved index. Synthesize completed results only.
5. Grep: `run_delegate` / `apply_conductor_rewrite` unchanged; no `plan_sequential`.
