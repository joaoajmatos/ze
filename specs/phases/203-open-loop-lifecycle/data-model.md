# Data Model: Open-Loop Lifecycle (phase 203)

No schema change and no migration (research R13). This file describes the existing rows, the event rules that now own them, and the new in-memory types.

## Rows (unchanged)

| Table | Owner | What an event writes |
|---|---|---|
| `open_loops` | ze-worldstate (`zw`) | state, confidence (with `confidence_prior` / `confidence_changed_at` through the confidence stamp), `confirmed_at`, `closed_at`, `drift_deadline`, `drift_rationale`, `dismissed_evidence_fingerprint`, `reminder_id`, `goal_id`, `updated_at` |
| `memory_relationships` | ze-memory (`zm`), loop rows only | `open_loop —derived_from→ <evidence>` (evidence links), `entity —has_open_loop→ open_loop` (entity links) |
| `open_loop_sources` | ze-worldstate (`zw003`) | origin rows (on create) and corroboration rows (`promoted`, `same_concern`, `model`, `latency_ms`) |

Readers keep reading the same rows: REST lists, matching, surfacing, `PriorityView`, the composer, screen resolvers, portability export.

## States

`suspected (S) → active (A) → drifting (D) → closed (C) | dropped (X)`. C and X are terminal.

## Events and rules (`lifecycle/rules.py`, `EVENT_RULES`)

"Refused" raises `InvalidLoopTransitionError` (REST 409) unless the row says otherwise. A missing loop raises `LoopNotFoundError` (REST 404). Every row below is one transaction (research R2).

| Event | S | A | D | C | X | Writes, in the one transaction |
|---|---|---|---|---|---|---|
| `CREATE_SUSPECTED` | — (new row: S) | | | | | contribution with evidence and entities; `INSERT` at confidence 0.3; evidence links; entity links; origin source when a key is known |
| `CREATE_DECLARED` | — (new row: A) | | | | | contribution with evidence and entities; `INSERT` with the declared stamp (window from the caller, default 7); evidence links; entity links; origin source when a key is known |
| `CONFIRM` | → A | refused | refused | refused | refused | declared stamp, window 7 |
| `TRACK` | → A (outcome `confirmed`) | → A (`reinforced`) | → A (`revived`) | refused | refused | S, D: declared stamp, window from the caller; A: confidence `max(c, 0.9)` only, deadline untouched; all: entity links |
| `NOTE_EVIDENCE` | S | A | D | refused | refused | evidence links; entity links; A with evidence: deadline `GREATEST(COALESCE(deadline, now()), now() + 7d)` (170) |
| `CORROBORATE` | S | refused | refused | refused | refused | evidence links; entity links; corroboration source row; confidence `min(0.6, 1-(1-c)(1-0.5·s))`. A duplicate source key writes no confidence (outcome `duplicate_source`) |
| `PROMOTE` | → A | lost race | lost race | refused | refused | evidence links; entity links; corroboration source row (`promoted = true` only on S); S: stamp with confidence `GREATEST(c, 0.7)`, window 7. A, D (another inflow promoted first): source row with `promoted = false`, no confidence or state write (outcome `lost_race`) |
| `RESOLVE` | → C | → C | → C | no change (`None`) | no change (`None`) | `closed_at`; evidence links. Never a fingerprint (the loop was done, not wrong) |
| `CLOSE` | refused | → C | → C | refused | refused | `closed_at` |
| `DROP` | → X | → X | → X | refused | refused | `closed_at`; fingerprint of the loop's evidence, read under the row lock |
| `EXPIRE` | → X | no change (`None`) | no change (`None`) | no change (`None`) | no change (`None`) | `closed_at`; fingerprint, as `DROP` |
| `LINK` | S | A | D | no change (`False`) | no change (`False`) | `reminder_id` / `goal_id`, set once, never overwritten; returns whether anything changed |
| `DECAY` | S (confidence only) | → D | D (confidence only) | C (confidence only) | X (confidence only) | confidence from the evidence-weighted profile; A only: state and the contradiction rationale |
| `DRIFT` | no change | → D if `drift_deadline <= now()` | no change | no change | no change | state; the absence rationale |

Rules the table states (FR-003):

- `A → D` only through `DECAY` and `DRIFT`.
- `D → A` only through `TRACK`.
- `S → C` only through `RESOLVE`.
- `S → A` only through `CONFIRM`, `TRACK` and `PROMOTE`.

"No change" events (`EXPIRE`, `DRIFT`, `RESOLVE`, `LINK` on the wrong state) return without raising: a sweep or an inflow raced another event, which is normal. "Refused" events are a caller asking for something the loop cannot do.

## The declared stamp (`rules.DeclaredStamp`)

| Field | Value |
|---|---|
| confidence | 0.9 (`DeclaredStamp.CONFIDENCE`) through the confidence stamp, so `confidence_prior` records a real change |
| `confirmed_at` | `now()` |
| `drift_deadline` | `now() + window` (default 7 days, `DeclaredStamp.DEFAULT_WINDOW_DAYS`) |
| `drift_rationale` | `NULL` |

Used by `CREATE_DECLARED`, `CONFIRM`, `TRACK` (S and D) and, with its own confidence expression `GREATEST(confidence, 0.7)`, `PROMOTE`.

## New types

### `CommitDecision` (`ze_worldstate/decision.py`, frozen dataclass)

| Field | Type | Notes |
|---|---|---|
| `kind` | `CommitKind` = `resolve \| create_declared \| create_suspected \| hold \| fallback` | |
| `reason` | `str` | for the log and the trace |
| `consumed` | `frozenset[str]` | judgment question ids the decision used |
| `title` | `str \| None` | set only by the 109 gate |
| `window_days` | `int \| None` | set only by the 109 gate |

`GateKind` = `resolve | create_suspected | hold | fallback` is what `loop_judge.decide` returns.

### `CommitResult` (`decision.py`, frozen dataclass)

| Field | Type |
|---|---|
| `outcome` | `created \| matched \| resolved \| no_match \| no_title \| held \| dismissed \| error` |
| `reason` | `str` |
| `loops` | `tuple[OpenLoop, ...]` |

`dismissed` is a suspected create blocked by a dropped loop's matching fingerprint (FR-011 of phase 109).

### `LoopAdmission` (`types.py`, changed)

| Field | Change |
|---|---|
| `decision` | type becomes `CommitDecision` |
| `text`, `inflow` | new constructor fields |
| `source` | becomes a constructor field (never set after construction) |
| `commit` | removed |
| `judgment` | 202's single record; untouched by 203 |

### `IntakeOutcome.kind` (`commitment_judge.py`, changed)

The three loop kinds become `resolve`, `create_declared`, `create_suspected` (research R6, spec Clarifications 2026-10-26). The others (`persist_fact`, `link`, `hold`, `fallback`) are unchanged.

### Removed

`LoopGateDecision`, `loop_judge.DecisionKind`, `types.DECLARED_CONFIDENCE`, `drift.DEFAULT_DRIFT_WINDOW_DAYS`, `drift.compute_drift_deadline`, `store._ALLOWED_TRANSITIONS`, `store._USER_ASKED_TRANSITIONS`, and the store write methods: `create`, `transition`, `resolve`, `link`, `link_entity`, `link_evidence`, `set_confidence`, `set_dismissed_evidence_fingerprint`, `set_drift_deadline`, `set_drift_rationale`, `record_corroboration`, `stamp_declared`, `add_source`, `promote`, `mark_source_promoted`. Modules `review.py` and `decay.py` are deleted.
