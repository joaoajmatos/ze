# Research: Loop Track Tool

## R1 — Why the loop is created in the tool, not by the post-turn gate
The 168 gate runs after the reply is written (`write_memory`), judges with calibrated bars and may hold. A tool result is the only evidence the agent can have *before* it speaks. Keeping creation in the gate would leave the honesty hole open. Rejected: making the agent say "I'll try to track it" (hedging, still untrue when held).

## R2 — Why not reuse `propose_loop_candidates(provenance="user_declared")`
It always calls `_create_declared_loop`, which bypasses matching (a second identical ask makes a second loop), derives the title from raw text (`text.strip()`), and needs an `LLMClient` and `admission` plumbing the tool does not need. The tracker reuses the building blocks (`loop_to_contribution`, `submit_and_detect_collisions`, `find_matching_loop`) and leaves `extraction.py` untouched.

## R3 — Gate skip vs dedup (user chose skip)
The 168 gate sees the same user text, answers `explicit_declaration`, and `_create_declared_loop` does no matching, so without a skip a track turn makes two loops. Dedup inside `_create_declared_loop` would fix that but changes 168 behavior for every inflow. The skip mirrors 148's `identities_from_remember_calls` and also saves a System One call. Trade-off, accepted by the user: a `resolves_existing` signal in the same message is not acted on that turn.

## R4 — Where the skip predicate lives
`write_memory` is in `ze_core`, which must not import `ze_worldstate`. `flatten_tool_calls` and `tool_payload` already live in `ze_agents/nested_tools.py` and the close/drop honesty check uses them. `track_loop_succeeded()` goes there. It matches on `tool_name == "track_loop"` and payload `ok is True`, so it also sees calls nested in `delegate_to_agent` results.

## R5 — Drift eligibility finding (F1): inert until phase 170
`PostgresLoopStore.list_drift_candidates` selects `state='active' AND drift_deadline IS NOT NULL AND updated_at <= confirmed_at`. `confirmed_at` is set in Python (`_create_declared_loop`, `transition`) and `updated_at = now()` is set later in SQL (`set_drift_deadline`, `transition`), so by this reading no loop is ever a drift candidate. Unverified on a live database. Drift is inert until phase 170 adds `last_activity_at` (`specs/arch/executive-function.md`, F1). Phase 169 does not fix it. `stamp_declared` only makes the track/confirm/revive write exact (same `now()` for both columns); a SQL-text unit test pins that shape. 170 may replace the method.

## R6 — `window_days` typing
`ToolSpec.llm_schema` skips any parameter whose annotation is not in `{str,int,float,bool,list,dict}`. `int | None` would vanish from the schema, so the model could never pass it. Use `window_days: int = 0`; 0 means default.

## R7 — Claim patterns and false positives
`enforce_domain_cancel_confirmations` is shared with the goals agent. Radar-style phrases ("keeping an eye on your goal") would be stripped there. So the family is opt-in via `strip_track_claims`, enabled only by `LoopsAgent`. Sentences containing `?` are never claims (offers). The patterns are deliberately narrow: radar/"keep an eye"/"tracking this"/"fico atento"/"no meu radar"/"vou acompanhar". The test table in the contract is the acceptance list; the engineer may widen patterns only by adding rows first.

## R8 — Capability and confirmation
`Mode.AUTONOMOUS` on the one `manage` intent already governs `close_loop`/`drop_loop`. A tracked loop is private, user-requested and undoable with `drop_loop`. No `constraint_gate`: it is for tools that must honor stored user constraints (calendar), and a loop carries none. Budget checker (113) composes at `capability_check` and is unaffected.

## R9 — Reversible, but Retry stays off
165 reads the declaration: reversible actions still make Retry unavailable ("Retry does not undo actions"). That is the right outcome: a retried turn would call `track_loop` again and report `reinforced`, which hides the first write.

## R10 — Routing
`routing_criteria` already routes "keep it on my radar" to loops (167 R9). Add one phrase about tracking to keep the E5 `description` and the Choice text aligned. Training rows only; held-out files and bars untouched. A turn the router sends to companion stays on the 168 path.

## R11 — Companion/conductor replies
When the conductor delegates to `loops` and then writes its own final reply, the conductor text could repeat the claim. The loops agent's own reply is enforced; the conductor's synthesis is governed by phases 151-156 rules and is out of scope. A conductor eval row is not added because 167's routing sends single-specialist loop asks directly.

## R12 — Live eval result

Run by Tally on 2026-10-13 against branch `169-loop-track-tool` @ `c440cf9f` with `make dev-eval`.

- **`track_loop`: pass in all three scenarios** (`loops_track_then_list_en`, `loops_track_then_list_pt`, `loops_track_twice_no_duplicate`) and in a manual check. After asking twice, `open_loops` held one row: `active`, confidence 0.9, `user_declared`, no duplicate. The held-out routing files are untouched.
- **Flaky routing, not a 169 defect.** The EN turn-2 prompt "what am I still sitting with?" routed to `companion` once (E5 gap 0.029, narrow). A rerun routed to `loops`. Phase 171's E5 open-query detector targets this.
- **Runner limitation, pre-existing.** For multi-turn scenarios the judge sees only the last turn's tool calls (`ze_eval/runner.py` lines 336-355), so the `track_loop` call in turn 1 is proven by the `verify` row, as the plan said.
