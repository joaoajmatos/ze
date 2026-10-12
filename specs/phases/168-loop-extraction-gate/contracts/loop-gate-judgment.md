# Contract: loop gate judgment

## Questions (fixed ids, all `noul`)
| id | asked when | meaning |
|---|---|---|
| `is_open_concern` | always | text implies an unfinished commitment, task or concern |
| `resolves_existing` | always | text reports a previously open commitment as done |
| `explicit_declaration` | provenance `conversation` only | the user themselves declares the commitment |

Nouls carry instructions only (no criteria). Wording is in research R10.

## Decision table (pure `decide(result, cfg, provenance)`)
Evaluated top to bottom (row 0 is applied by `LoopInflow.admit` before any request). Rows with a `skip` or `invalid` outcome never reach a later row.

| # | Condition | Decision |
|---|---|---|
| 0 | conversation text is trivial (`is_trivial_turn`) or any text is empty | `hold` (`trivial`); no request, no rows, no Haiku, `commit` is `None` |
| 1 | result outcome `skip` | `fallback` (reason = skip reason) |
| 2 | a question that was asked has no valid Noul answer | `fallback` (`invalid_answer`) |
| 3 | any bar is `None` | `fallback` (`uncalibrated`) |
| 4 | `resolves_existing` ≥ `resolves_hold` | `resolve`; consumed = `resolves_existing` |
| 5 | `is_open_concern` < `loop_hold` | `hold` (`not_open_concern`); consumed = both gates |
| 6 | conversation and `explicit_declaration` ≥ `explicit_hold` | `create_declared`; consumed = all asked |
| 7 | otherwise | `create_suspected`; consumed = all asked |

Rows 1 to 3 run the 109 Haiku gate. Rows 4 to 7 never run it. At-the-bar counts as positive. A Noul around 0.5 means undecided and is below any sensible bar; no unsure band exists for Nouls.

## Writer (Haiku, after rows 4, 6, 7 only)
Input: the capped text and `kind` (`create` or `resolve`). Output JSON `{"title": str, "implied_window_days": int?}`; `implied_window_days` only for creates and only a positive whole number. Empty title or any failure: no loop is created or closed, warning logged. The writer never decides existence.

## Commit (code, unchanged semantics)
`resolve`: `find_matching_loop` over `suspected|active|drifting`, then `transition(..., closed)`. `create_declared`: `_create_declared_loop` (active, 0.9, `user_declared`, drift deadline). `create_suspected`: dismissal check (FR-011), existing-loop attach (FR-010), else new `suspected` 0.3 through `submit_and_detect_collisions`.

## Config
`system_one.surfaces.loop_gate` as in `data-model.md`. Enabled with any null bar: one warning per call, `fallback`. A missing client: `fallback`.
