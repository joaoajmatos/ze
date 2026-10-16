# Research: One Commitment Intake

- **Current split (verified in code):** `write_memory` runs `_run_fact_extractor` (163 request: `speech_act`, `family`, `biography`) and `_run_loop_admission` (168 request: three Nouls) in one `asyncio.gather`. Two requests, no shared answer. `tracking_earned` already suppresses the loop side after `track_loop`.
- **Why post-turn cannot create reminders:** the reminder and goal exist before `write_memory` runs, created by the agent's own tool. The intake can only decide about loops and links.
- **Tool results:** `set_reminder` returns `{id, label, fire_at, undo}`; `create_goal` returns `{id, title, milestones, gates, undo}`. Both have `error` keys on failure.
- **Dependency direction:** `ze-worldstate -> ze-memory`; the merged judge therefore lives in `ze-worldstate` (D-1).
- **Matching:** `find_matching_loop` is entity overlap first, E5 title cosine 0.75 second; reused for linking.
- **F4 evidence:** 24 live calls (executive-function Appendix A) are the seed for hard-negative rows in the calibration sets (not copied into the held-out set verbatim).
- **T020, 181 re-read (2026-10-16, branch `181-irreversible-write-confirmation`):** `success` semantics unchanged for our check. A parked or denied write is built with `success=False` and `gate="parked"` / `"denied"` / `"refused_over_cap"`; `success=True` only for an executed call. `turn_creation` reads `success` plus a non-error payload id, so a parked `set_reminder`/`create_goal` is not a creation. 181 adds `ToolCall.parked`, `child_loop`, `approval` (not read here). 181 does not touch `nested_tools.py` or `nodes/memory.py` on its branch.
