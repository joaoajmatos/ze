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

## Follow-ups (not in 172)

- Gate 170's `record_corroboration` on active loops with the same Noul.
- Fix the single-entity shortcut in `find_matching_loop` (below-bar match → separate loop).
- Choice over several candidate loops.
- Let held texts corroborate (title-less matching), user answer 4A.
