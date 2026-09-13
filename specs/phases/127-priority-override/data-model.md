# Data Model: User-Directed Priority Override

## `PriorityOverride` (new — owned by `ze-priority`, table `priority_overrides`)

The durable record of a user's reprioritization for one item. At most one active
(non-superseded) row per `(source_kind, source_id)` — a new instruction for the
same item supersedes the previous row rather than adding a second active one
(FR-012).

| Field | Type | Notes |
|---|---|---|
| `id` | `UUID` | primary key |
| `source_kind` | `Literal["loop", "goal", "hypothesis"]` | matches `ze_priority.types.SourceKind` — the item's origin among `PriorityView`'s three sources |
| `source_id` | `UUID` | the loop/goal/hypothesis id (`OpenLoop.id` / `Goal.id` / `Hypothesis.id`) |
| `anchor_source_kind` | `Literal["loop", "goal", "hypothesis"]` | the reference item's source (R3) |
| `anchor_source_id` | `UUID` | the reference item's id |
| `relation` | `Literal["above", "below"]` | requested position relative to the anchor (R3) |
| `pinned` | `bool` | `False` = decaying override (FR-008); `True` = durable pin (FR-009) |
| `submitted_at` | `datetime` | used both for FR-012/FR-014 ordering and R6's decay-weight calculation |
| `superseded_at` | `datetime \| None` | set when a later instruction for the same `(source_kind, source_id)` replaces this row (FR-012); superseded rows are excluded from ranking but retained for audit (SC-004) |
| `contribution_domain_id` | `UUID` | the id returned by `submit_and_detect_collisions`'s `write()` for this override's Contribution — links the row back to its audited Contribution (SC-004) |

**Validation / state rules**:
- Creating a new row for a `(source_kind, source_id)` that already has an active
  (`superseded_at IS NULL`) row sets that prior row's `superseded_at = now()` in
  the same transaction (FR-012).
- A row is excluded from ranking (R7) once its `source_kind`/`source_id` no
  longer appears in `PriorityView`'s current three source lists (FR-011) — this
  is a read-time filter, not a delete; the row is not resurrected if the item
  reappears later under the same id.
- `pinned=True` rows never decay (R6); `pinned=False` rows decay to weight `0`
  at `submitted_at + 48h` (R6), after which they are read-time-equivalent to
  having no active override (still present in storage for audit, but contribute
  no positional weight).

## `Reprioritization Contribution pair` (not persisted as a distinct type —
composed at submission time from existing `ze_plugin.contribution.Contribution`)

Two `Contribution` objects are submitted per reprioritization instruction,
per R1/R4:

| Field | User override contribution | Companion "Ze's own claim" contribution |
|---|---|---|
| `claim_kind` | `PRIORITY` | `PRIORITY` |
| `source_function` | `EXECUTIVE` | `EXECUTIVE` |
| `provenance` | `PROMPT_SUPPLIED` | `SYNTHESIZED` |
| `target_face` | `ACTIVE_CONCERNS` | `ACTIVE_CONCERNS` |
| `entity_ids` | `[source_id]` | `[source_id]` |
| `content` | human-readable requested relation (R3) | human-readable rendering of `PriorityView`'s current computed position for the same item |
| `confidence` | `Confidence(value=1.0 if pinned else decay_weight_at_submission, decay_profile=TIME_LINEAR)` | the item's existing `PriorityItem.priority` (`Confidence`) from `PriorityView.rank()` |

Both are submitted through `ze_collision.detect.submit_and_detect_collisions()`
(not bare `validate_and_submit`) so the collision side-channel (R1) fires. The
`write()` callback for the user override contribution persists the
`PriorityOverride` row above; the companion contribution's `write()` is a no-op
persistence (it exists purely to populate the collision candidate window — see
R1) returning a synthetic id.

## Ranking merge (read path, not persisted)

`PriorityView.rank()`'s unmodified `PriorityRanking.items` list is combined with
active `PriorityOverride` rows at render time (R7):

1. Fetch unmodified `PriorityRanking` from `PriorityView.rank()`.
2. Fetch active `PriorityOverride` rows (`superseded_at IS NULL`, item still
   present in the ranking) ordered by `submitted_at` ascending.
3. Apply each override in order: reposition its item adjacent to its anchor
   item's current displayed position, per `relation`, blended by decay weight
   (R6) — full weight fully repositions; partial weight interpolates between
   the unmodified position and the requested position.
4. For each item with an active override, compute whether its final displayed
   position disagrees with its unmodified `PriorityRanking` rank; attach this
   boolean (`overridden_from_computed: bool`) to the rendered row for FR-010's
   in-view indicator (R2) — computed fresh each render, independent of the
   collision log.

This merge is a pure function of `(PriorityRanking, list[PriorityOverride], now)`
— no new persisted "final order" state; the snapshot view is always recomputed
(R2/R6, Clarifications Session 2026-08-26 Q3).

## Existing types read, unchanged

- `ze_priority.types.PriorityItem` / `PriorityRanking` / `SourceKind` — read-only
  input to the merge above; no fields added.
- `ze_worldstate.types.OpenLoop`, `ze_automation.goals.types.Goal`/`StuckGoal`,
  `ze_correlation.types.Hypothesis` — read-only, used to resolve `source_id` →
  current title/state for FR-011's "item still exists" check and for rendering
  `source`/`title` in the snapshot view (FR-001).
