# Research: Corroboration Promotion (172)

All decisions below were accepted by the user on 2026-10-12 (spec Clarifications) or follow from code read at `0b9845b1` plus the pinned 170 and 171 specs.

## R1 — Where corroboration hooks in

**Decision**: Two call sites, both in `ze_worldstate/extraction.py`, both only when the matched loop is `suspected`:
1. `_create_suspected_loop`, the branch where `find_matching_loop(..., states=["suspected","active","drifting"])` returns `existing`.
2. The declared-path match that Phase 170 adds before `_create_declared_loop` creates (170 FR-012).

Both call one new function, `corroborate_match(...)` in a new module `ze_worldstate/corroboration.py`, which returns after doing either the 170 behavior or the corroborate/promote effects.

**Rationale**: These are the only places where a gate-admitted text meets an existing suspected loop. Cairn (170 author) confirmed that 172 owns the suspected branch and that 170's `record_corroboration` acts on `active` only.

**Alternatives**: A separate post-commit sweep that pairs new evidence with suspected loops. Rejected: it would re-run matching, double the work and lose the source key at hand.

## R2 — Source keys

**Decision**: `SourceKey(inflow: str, ref: str)` (frozen dataclass in `ze_worldstate/types.py`).

| Inflow | `ref` | Where it is read |
|---|---|---|
| conversation | `configurable["thread_id"]` | `LoopInflow.admit(configurable, prompt)` already receives `configurable` (168 deletes it with `del`; 172 reads it) |
| email | `msg.thread_id or msg.message_id` | `ze_messenger/inbound/processor.py` L157 |
| calendar | `signal.external_ref` | `ze_calendar/jobs/calendar_reminder.py` L61 (calendar loops have no evidence after 170; this is their identity) |
| ingestion | `ingestion_id` | `ze_ingestion/sink.py` L67 |

Plugins pass `source_ref: str | None` as a keyword to the opaque extractor callable; they never import `ze_worldstate` (dependency rule). An empty or `None` ref means "no key".

**Rationale**: D2 requires independence "defined in code (different source type or different thread/document)". Each inflow already holds a stable id.

**Alternatives**: Different inflow only (rejected by the user, 1A); also a different email sender (rejected, 1A).

## R3 — Independence rule

**Decision**: Pure function `is_independent(key, new_evidence, loop_sources, loop_evidence, dropped_sources) -> tuple[bool, str]` in `corroboration.py`, returning a reason for the log (`no_key`, `same_source`, `same_evidence`, `dropped_source`, `independent`). Inputs are fetched by the caller:
- `loop_sources`: `LoopStore.list_sources(loop_id)`.
- `loop_evidence`: `LoopStore.list_evidence(loop_id)` (exists).
- `dropped_sources`: sources of the `dropped` loop that `find_matching_loop(..., states=["dropped"])` returns for the same title, which `_create_suspected_loop` already computes as `dismissed`. On the declared path the same lookup is added.

Independence is checked **before** linking the new evidence, because linking would make every text look "same evidence".

**Rationale**: Code owns policy (ADR pin 2). Checking before any System One request saves calls on the common non-independent case (a thread that keeps talking about the same thing).

## R4 — The question

**Decision**: One Noul, id `same_concern`, in `ze_worldstate/corroboration_judge.py`:

> "Is the text about the same unfinished matter as the open item named in `loop`? The same person, place or topic alone is not enough; it must be the same thing to do, decide, answer or follow up on."

State: `{"loop": <title, cap 200>, "source": <inflow>, <loop_judge key for inflow>: <text capped with the 168 cap>}`. Reuses `loop_judge.build_state` for the text half so caps stay in one place. Nouls take no criteria (168 note), so the title goes in state.

**Rationale**: Pin 7 (one narrow question). A Choice over several candidates was considered; `find_matching_loop` already returns one candidate, and a Choice would need its own option-order randomization in eval and a different calibration shape. Recorded as a follow-up if the single-entity shortcut is fixed.

**Wording is a plan-time choice**: the ENG lead may change it on the tuned set only, before the held-out run (FR-020).

## R5 — Confidence arithmetic

**Decision** (code constants in `corroboration.py`):
- `CORROBORATION_WEIGHT = 0.5`
- `CORROBORATED_CAP = 0.6` (a suspected loop never reaches the promoted level without promotion)
- `PROMOTED_CONFIDENCE = 0.7` (below user-stated 0.9; 171 makes confirm 0.9 too)
- `PROMOTED_WINDOW_DAYS = 7` (= `drift.DEFAULT_DRIFT_WINDOW_DAYS`; import it, do not duplicate)

Corroborate: `c' = min(CORROBORATED_CAP, 1 − (1 − c)(1 − W·s))`. From 0.3 at s = 0.8: `1 − 0.7·0.6 = 0.58`. A second one at 0.8: capped at 0.6.

**Rationale**: Pin 2 (arithmetic is code). Noisy-OR is monotone, bounded, and uses the score as a weight, so a 0.76 counts less than a 0.98. The cap keeps "corroborated" and "promoted" distinct on the ranking.

**Alternatives**: Fixed +0.15 step (ignores the score); promotion by count of corroborations (a rule that cannot be calibrated on pairs). Both rejected.

## R6 — Storage: `open_loop_sources` (zw003)

**Decision**: New table, ze-worldstate chain, `zw003_open_loop_sources.py`, `down_revision = "zw002"`. Schema in `data-model.md`. Unique `(loop_id, inflow, source_ref)`; `ON DELETE CASCADE` from `open_loops`. Insert uses `ON CONFLICT DO NOTHING RETURNING id`; a `None` return means the key was already there and the judgment does not count (race-safe idempotency).

`zw003` is free: 170 adds no migration (Cairn), 171 adds no schema change (Sextant).

**Alternatives**:
- Store the key on the `derived_from` evidence edge in `memory_relationships`. Rejected: that table is ze-memory's, evidence and sources are not 1:1 (calendar has a key but no evidence), and the score has no home there.
- A JSONB column on `open_loops`. Rejected: no unique constraint, racy appends.

## R7 — Promotion write

**Decision**: `LoopStore.promote(loop_id, *, confidence, window_days) -> OpenLoop | None`, one statement:

```sql
UPDATE open_loops
SET state='active', confidence=GREATEST(confidence,$2), confirmed_at=now(),
    drift_deadline=now() + make_interval(days => $3), drift_rationale=NULL, updated_at=now()
WHERE id=$1 AND state='suspected'
RETURNING *
```

`None` means another writer changed the state first (user confirm via 171, `track_loop` via 169, drop). Then `LoopStore.mark_source_promoted(source_id)` runs only on a non-`None` result. Not through `transition()`: `transition` reads then writes (not atomic) and has no confidence or deadline.

**Rationale**: The 170 drift predicate is `state='active' AND drift_deadline <= now()`, so a promoted loop drifts after 7 quiet days like any other active loop. One `now()` for `confirmed_at` and the deadline matches 169's `stamp_declared` field set (minus confidence 0.9).

## R8 — Judgments: durable row plus log, not the trace

**Decision** (user 5A): The conversation commit is fire-and-forget after `write_memory` returns (168 FR-006), so `MessageTrace.judgments` cannot receive these rows. Each counted judgment is stored on its source row (`same_concern`, `model`, `latency_ms`). Every judgment, counted or not, emits `corroboration_judgment` with `loop_id`, `inflow`, `outcome`, `reason`, `score`, `latency_ms`, `skip_reason`. Non-independent matches emit `corroboration_skipped` at debug with the independence reason.

## R9 — Calibration baseline

**Decision**: E5 title cosine at `matching.DEFAULT_SIMILARITY_THRESHOLD` (0.75) between `new_title` (a hand-written title, standing in for the Haiku title) and `loop_title`. The script loads the real embedder (`ze_core.embeddings` singleton, `query:`/`passage:` prefixes exactly as `find_matching_loop` uses `embedder.encode`). It cannot simulate the single-entity shortcut (no graph); the `same_entity_other` rows stand in for it, and the report labels them.

Acceptance (user): per language on the held-out set: zero false promotions; corroborate precision ≥ 0.9 and ≥ E5 precision; corroborate recall ≥ E5 recall − 0.05.

**Grid**: `corroborate_hold` and `promote_hold` each over 0.50–0.95 step 0.05 with `corroborate_hold ≤ promote_hold`. Suggested bars: the smallest `promote_hold` with zero false promotions on the tuned set plus one grid step of margin; the `corroborate_hold` that maximizes recall subject to precision ≥ 0.9, then one step of margin.

## R10 — What the user sees

**Decision** (user 6A): REST fields and one label on 171's `/loops` page row. No push, notification or chat line. Label text, EN: "Promoted · seen in: chat, email". Inflow labels: conversation → "chat", email → "email", calendar → "calendar", ingestion → "a document". ze-web has no i18n layer for this widget today; follow whatever 171 ships.

## R11 — Calibration data authoring

**Decision**: The held-out file is written first and committed before any live run, by the ENG lead (not a junior: hard negatives and cross-language pairs need judgment). Row kinds: `same` (direct restatement), `paraphrase`, `cross_lingual` (title EN, text PT or the reverse), `same_entity_other`, `same_topic_other`, `unrelated`. At least a third hard negatives per language. Each inflow at least 4 rows per language in the tuned set and 2 in the held-out set.

**Written 2026-10-13 by the Spec Architect** (T029 held-out `57a10e41`, committed before the tuned file; T030 tuned). Held-out: 24 EN, 23 PT. Tuned: 42 EN, 42 PT; 15 hard negatives per language; 0 texts shared. `same` rows are direct restatements (expected to promote); `paraphrase` rows are indirect or weaker mentions (expected to corroborate at least). `same_entity_other` rows are the wrong-merge case: same person, product or institution as the loop, different matter. `lang` is the language of `text`; `cross_lingual` rows have a loop title in the other language. No live run has been made.

## Follow-ups (not in 172)

- Gate 170's `record_corroboration` on active loops with the same Noul.
- Fix the single-entity shortcut in `find_matching_loop` (below-bar match → separate loop).
- Choice over several candidate loops.
- Derive the ingestion source key from the document or URL instead of the run id. `ze_ingestion/pipeline.py` mints a fresh `uuid4` per run, so a re-ingest of the same document gets a new key and new evidence ids and is judged independent. The key guards only a repeated push of the same ingestion id. Known limitation of FR-001 while the surface is off.
- Let held texts corroborate (title-less matching), user answer 4A.

## Tuning notes (T033)

Run 2026-10-15 by the ENG lead with `make calibrate-corroboration`. System One model as configured: `typesafe/jev-1.13`. Rows: 84 tuned (42 EN, 42 PT), 47 held-out (24 EN, 23 PT). Question wording unchanged from R4 (no iteration was needed).

**Tuned set.** Zero false promotions at every bar pair on the grid. Corroborate precision 1.000 at every bar. Recall (both languages): 0.95 at `corroborate_hold` 0.50, 0.93 at 0.55, 0.91 at 0.60 to 0.70, 0.80 at 0.75, 0.73 at 0.80. The reliability table is clean: every score of 0.5 or more is a gold-same row (40 of 40); every negative scores below 0.5; the grey zone 0.2 to 0.5 holds three rows, one positive each in the 0.2 and 0.4 bins. Misses at 0.55: `t-en-017` (0.46), `t-pt-016` (0.54), `t-pt-017` (0.23), all paraphrases.

**Bar choice.** Research R9's literal rule returns `0.55 / 0.55` (smallest zero-false-promotion `promote_hold` 0.50 plus one step). That collapses the two tiers, so every counted match would promote. Because no tuned negative scores above 0.5, the grid cannot separate corroborate from promote by false promotions. The ENG lead chose `corroborate_hold 0.6` and `promote_hold 0.8` on the tuned set alone: promotion changes loop state and is the costlier error, scores of 0.8 and above are 32 of 32 gold-same, and recall at 0.6 is 0.91. This is a deliberate departure from R9's arithmetic, made before the held-out run.

**E5 baseline.** Title cosine at 0.75 matches every row (tuned: P 0.524, R 1.000; held-out: P 0.574, R 1.000). E5 title similarity cannot tell the same matter from the same person, so the baseline's recall is a ceiling that the recall clause compares against, and its precision is the bar the system clears easily.

**Held-out verdict (one run, bars 0.6 / 0.8).**

| Lang | Counted | P | R | False promotions | Verdict |
|---|---|---|---|---|---|
| EN | 14 of 14 positives | 1.000 | 1.000 | 0 | ENABLE |
| PT | 12 of 13 positives | 1.000 | 0.923 | 0 | KEEP OFF: recall 0.923 < E5 1.000 - 0.05 |
| Overall | | 1.000 | 0.963 | 0 | KEEP OFF |

The surface ships off with null bars. PT misses one positive row. Under the spec's rule the surface turns on only when both languages pass. The held-out file is now spent for these bars and this wording. Any change to wording or bars needs a new held-out file before another verdict (FR-020).

**What would change the verdict.** The recall clause is relative to an E5 baseline that matches everything, so with a small set one PT miss fails it. Follow-ups for the Maestro to decide: (1) a larger held-out set per language so one row is less than 0.05 of recall; (2) amend the recall clause to an absolute floor (for example recall at least 0.9) while keeping the precision and false-promotion clauses; (3) a lower `corroborate_hold` such as 0.5 or 0.55, which recovers about two points of tuned recall at no precision cost on the tuned set. None of these was applied.
