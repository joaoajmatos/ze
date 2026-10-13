# Research: Loop Confirmation Path (171)

Each entry: decision, rationale, alternatives. R1–R6 are the user's answers (Q1–Q6, 2026-10-12); R7 onward are Spec Architect decisions.

## R1 — Where the review list lives (Q1)

- **Decision**: New page `/loops` ("Open loops"), Automation nav group after Priority, desktop nav only. The page slice is a thin wrapper around `widgets/loop-review`.
- **Rationale**: `LoopReviewList` is a full `ListPage` with its own empty, loading and error states; the Priority page is a drag-ordered ranking that 170 is also editing (`sources_failed` notice). A separate page avoids a merge conflict with 170 and keeps each page single-purpose.
- **Alternatives**: a section on the Priority page (couples two list paradigms, conflicts with 170); both (twice the surface for one list).

## R2 — Who words the resume question (Q2)

- **Decision**: Code selects at most 3 loops and records the offer; the recap tells the speaking agent to end with one short question in the user's language; it must not say they are tracked.
- **Rationale**: Ze is EN + PT, and there is no stored user locale. The speaking model already writes in the user's language. A fixed English suffix would be wrong half the time. Every agent renders the recap through `BaseAgent._build_system_prompt`, so no per-agent change is needed.
- **Alternatives**: deterministic English suffix (wrong language); inline Keep/Drop buttons (needs a new ze-ui primitive and an action channel; belongs with the 176 Today surface).
- **Known cost**: the code cannot verify the model asked. The trace records `loop_offer_ids`, so a skipped question is visible, and the page stays as the fallback.

## R3 — Re-offer cooldown (Q3)

- **Decision**: 168 hours (7 days) per loop, through `push_log.was_sent_within_hours("worldstate_loop_offer:<id>", 168)`. With the 14-day `StaleSuspicionJob`, a loop is offered at most twice. Silence changes nothing; "no" drops.
- **Rationale**: `push_log` already backs inline-mention cooldowns (`worldstate_loop_inline:<id>`, 110/132); no migration. Two chances before expiry balance nagging against loss.
- **Alternatives**: once only (one missed session loses the loop); every resume (nagging).
- **Failure mode**: if the push-log read fails, no offers that turn (fail closed). Reason: failing open would re-offer the same loops on every resume while the store is down.

## R4 — What a confirm writes (Q4)

- **Decision**: `review.confirm_loop` = `transition(id, "active")` then `stamp_declared(id, confidence=DECLARED_CONFIDENCE, deadline=now + DEFAULT_DRIFT_WINDOW_DAYS)`. Provenance and claim kind unchanged.
- **Rationale**: Today a confirmed loop keeps 0.3 and `score_loop` ranks it by confidence, so confirmation barely moves it. 169's `track_loop` already writes exactly this on a matching suspected loop; one meaning for "the user said keep this" across page, REST, chat and track. `stamp_declared` sets `confirmed_at` and `updated_at` from one `now()`, which is what 170's deadline-only drift predicate expects.
- **Alternatives**: keep 0.3 (confirm is cosmetic); change provenance to `user_declared` (loses the honest origin — the user confirmed an inference, they did not state it).
- **Transition note**: `transition` sets `confirmed_at = now` for `→ active`, then `stamp_declared` overwrites it with the same-statement `now()`. Two statements, not atomic; a crash between them leaves an active loop at 0.3 without a deadline, which the user can fix by asking to track it (169 reinforces it to 0.9). Accepted (same as 169's confirm path).

## R5 — Language-neutral "what's open" (Q5)

- **Decision**: `OpenQueryDetector` in `ze_priority/open_query.py`. Holds about 15 EN and 15 PT example questions. Embeds them once, lazily, with the same call `fetch_context` uses for the prompt (`embedder.encode`, which prefixes `passage:`), so both sides are in the same E5 space. Detects when `max(cosine) >= OPEN_QUERY_THRESHOLD`.
- **Rationale**: the prompt embedding already exists (computed for retrieval), so the check costs one small matrix product. Multilingual E5 handles EN and PT and generalises to paraphrases a regex misses. No System One call per turn.
- **Calibration**: `eval/calibration/open_query.jsonl` (tuned: at least 40 EN + 40 PT rows, roughly half positives; hard negatives include "what time does the shop open", "is the pharmacy open on Sunday", "open the file", "abre a janela", "a vaga ainda está aberta?", "what's on TV", "o que tenho para jantar"). `open_query_holdout.jsonl` (at least 20 EN + 20 PT, written before any tuning, never tuned on). `eval/calibration/open_query.py`: `--set tuned` sweeps thresholds 0.80–0.95 by 0.005 and prints recall and false-positive rate per language, suggesting the lowest threshold with tuned FPR ≤ 0.02; `--set holdout --threshold T` is the single verdict run (PASS if recall ≥ 0.9 and FPR ≤ 0.05 per language); `--check-sets` validates file shape. Local model only, no credits. If held-out fails, the ENG lead edits the example list or threshold on the tuned set, writes a new held-out file (`open_query_holdout2.jsonl`), and reruns once; the verdict and threshold go into this file under "Verdict".
- **Alternatives**: Portuguese regex patterns (cheap, still language-bound, misses paraphrases); a System One Noul per turn (a paid call on every turn for a rare intent); asking the router (routing chooses an agent, while "what's open" is a context note for any agent).
- **E5 caveat**: E5 cosines for unrelated short texts sit around 0.7–0.8, so the useful threshold is high (expected 0.86–0.92). The sweep range reflects that. Phase 160 retuned routing thresholds for E5 for the same reason.

## R6 — Caps (Q6)

- **Decision**: `RECAP_LIMIT = 5`, `OPEN_QUERY_LIMIT = 10`, `OFFER_LIMIT = 3`, constants in `ze_priority/turn.py`. Applied after the 127 merge, so pins and overrides come first.
- **Rationale**: the recap is unrequested context; the explicit question deserves more. Not configurable (no reader for a config key yet; 170 just removed unread keys).

## R7 — Confirm by id, not by title

- **Decision**: new `confirm_loop(loop_id)` tool; reuse `review.confirm_loop`.
- **Rationale**: `track_loop` matches by entity overlap and E5 title similarity and could confirm a different loop than the offered one. The offered loop has an id the loops agent gets from `list_open_loops`. Same shape as `close_loop` / `drop_loop`.
- **Honesty**: `tracking_earned` (renamed from 169's `track_loop_succeeded`) is true for a `track_loop` with `ok: true` or a `confirm_loop` with `ok: true`. The 169 `_TRACK_CLAIM` family then keeps "I'll keep track of X" after a confirm. The 168 gate skip in `write_memory` uses the same predicate, so a confirm turn does not also run the gate.
- **Reversibility**: `REVERSIBLE`, `undo_tool="drop_loop"`, undo note "Dropping the loop removes it; it does not return it to suspected." Retry (165) then refuses such a turn, which is correct.

## R8 — Return shape of `confirm_loop`

- **Decision**: `{ok: true, id, title, state}` / `{ok: false, error}`, matching `track_loop` (169), not the `{error}`-only shape of `close_loop`/`drop_loop`.
- **Rationale**: `tracking_earned` reads `ok is True`. Changing close/drop is out of scope (their guard reads `loop_review_earned`).

## R9 — Where the offer selection lives

- **Decision**: `TurnSurfacing.resume_loop_offers` in `ze-priority`.
- **Rationale**: `ze_core` reaches executive surfaces only through the duck-typed `turn_surfacer`; `TurnSurfacing` already holds `loop_store` and `push_log` and owns the other recap inputs. Suspected loops are not `PriorityView` items (it ranks active/drifting only), so this reads the store directly; that is fine because offers are not a ranking.
- **Alternatives**: a new `ze_worldstate` service plus a new `configurable` key (one more wire for no gain); putting suspected loops into `PriorityView` (changes ranking; 175's job).

## R10 — Evals

- **Decision**: two eval scenarios ("What's still on my plate?", "O que tenho em aberto?") in `eval/scenarios/loops.yaml` with judge criteria requiring a list of open items or an honest "nothing open"; four routing training rows (EN/PT confirm and drop by title → `loops`). No held-out edits.
- **Rationale**: the eval runner has no setup step and no way to fake a session gap, so the resume offer and chat confirm are covered by graph-level unit tests and the pg test instead.

## Verdict

**Not a clean verdict.** Read the runs in order; the detector changed between them.

`PT_SIMILARITY_OFFSET = 0.05` (E5 scores Portuguese pairs about 0.05 higher, including job-vacancy negatives, so Portuguese example similarities are lowered by it) and threshold 0.88 were chosen on the **tuned** set before any held-out run. An attempt to ship without the offset was rejected: at 0.88 it gave Portuguese false positives of 0.600 (held-out 1) and 0.333 (held-out 2) and 0.682 on the tuned set, so it was tried and not kept.

| Run | Detector at that time | EN recall / FPR | PT recall / FPR |
|---|---|---|---|
| held-out 1, threshold 0.88 | 14 EN + 22 PT examples + offset | 0.900 / 0.000 | 0.800 / 0.000 (original bar missed) |
| held-out 2 (R5 rerun), threshold 0.88 | the same plus six list-style examples added **after seeing held-out 1's misses** | 0.917 / 0.000 | 0.667 / 0.000 (original bar missed) |
| **shipped detector**, both sets, one run, threshold 0.88 | the six post-hoc examples removed; five examples reworded because they equalled tuned-set texts verbatim; nothing else changed | held-out 1: 0.900 / 0.000; held-out 2: 0.917 / 0.000 | held-out 1: 0.800 / 0.000; held-out 2: 0.667 / 0.000 |

Tuned set at the shipped detector: EN 0.955 / 0.000, PT 0.818 / 0.000. The shipped detector's numbers equal the first two rows, so the post-hoc examples changed nothing measurable on either set.

**Decision (user, 2026-10-13): ship at threshold 0.88 under an amended bar.** The original bar (recall >= 0.90 per language) was missed in Portuguese on both held-out sets. The amended bar (EN recall >= 0.90, PT recall >= 0.65, FPR <= 0.05 per language) was set after seeing those results, so this is not a clean pre-registered verdict, and both held-out sets are seen and cannot serve as one again. A missed detection is benign (the open-priorities note is not injected and the user can rephrase); a false positive is the costly error.

`tests/test_open_query_holdout.py` (slow) pins the shipped numbers against the amended bar. The offset is a Portuguese-only correction, so a third language would run uncorrected. Follow-up, not built here: a System One Noul `asks_what_is_open` to replace similarity; Portuguese needs it most.
