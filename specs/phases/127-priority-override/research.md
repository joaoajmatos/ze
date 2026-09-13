# Phase 0 Research: User-Directed Priority Override

## R1. How does a user's reprioritization pass Contribution licensing while still
being detectable as a collision against `PriorityView`'s own computed ranking?

**Problem**: `core/ze-plugin/ze_plugin/contribution.py`'s license table licenses
`ClaimKind.PRIORITY` to `SourceFunction.EXECUTIVE` only (this is a doctrine-mandated
closed set per the module docstring — "the seven cognitive functions ... from
`specs/arch/ze-doctrine.md`"). Any reprioritization Contribution, whether from the
drag path or the conversational path, **must** carry `source_function=EXECUTIVE` to
pass `validate_and_submit()`. But `ze_collision.detect._find_candidates()` skips any
candidate pair sharing the same `source_function` (`detect.py:63-64`, the FR-002/FR-007
rule from Phase 126) — so two `EXECUTIVE`-sourced contributions can never be logged as
colliding under the collision detector as it stands today. Since `PriorityView.rank()`
is currently a pure read path that never submits a Contribution at all, there is today
no "Ze's own computed Priority claim" object for a user's override to collide against
in the first place.

**Decision**: Two changes, both minimal and precedented:

1. **Provenance, not a new SourceFunction, carries the user-vs-executive distinction.**
   `core/ze-worldstate/ze_worldstate/contribution.py:12-16` already maps
   `LoopProvenance.USER_DECLARED → Provenance.PROMPT_SUPPLIED` for `OpenLoop`
   contributions — a direct precedent for "user-stated" intent expressed as
   `Provenance.PROMPT_SUPPLIED` under `SourceFunction.EXECUTIVE`, not as a new
   enum member. A reprioritization Contribution is therefore:
   `source_function=EXECUTIVE`, `claim_kind=PRIORITY`,
   `provenance=PROMPT_SUPPLIED`, `target_face=ACTIVE_CONCERNS` (the same face
   `OpenLoop` contributions already target, and the face `PriorityView` ranks
   items drawn from).

2. **`ze_collision.detect._find_candidates()`'s skip rule is narrowed from
   `source_function` equality to `(source_function, provenance)` equality.**
   When the user submits a reprioritization Contribution
   (`EXECUTIVE`/`PROMPT_SUPPLIED`), the reprioritization service also submits a
   companion Contribution representing `PriorityView`'s own current computed
   position for that same item: `source_function=EXECUTIVE`,
   `claim_kind=PRIORITY`, `provenance=SYNTHESIZED` (Ze's own inference, per
   `ze_agents.claims.Provenance`), `target_face=ACTIVE_CONCERNS`, `content`
   describing the computed rank. With the skip rule narrowed to the
   `(source_function, provenance)` pair, `EXECUTIVE`/`PROMPT_SUPPLIED` vs.
   `EXECUTIVE`/`SYNTHESIZED` is no longer skipped, so the NLI contradiction
   check in `_check_for_collisions` can fire and log a `CollisionLogEntry`
   when the user's requested position and Ze's own computed order genuinely
   disagree — this is the observable evidence Phase 126 is meant to receive
   (spec Overview, FR-010).

   FR-012's supersession carve-out (a second reprioritization from the same
   user for the same item is not a new collision) continues to hold under the
   narrowed rule for free: both the first and second user instructions share
   `(EXECUTIVE, PROMPT_SUPPLIED)`, so they still skip each other exactly as
   126's same-function rule always intended for a producer updating its own
   prior claim.

**Alternatives considered**:
- *Add `SourceFunction.USER`.* Rejected — `SourceFunction` is doctrine-mandated
  to the seven cognitive functions Ze itself implements (per the module
  docstring); the user is external to that model, not an eighth function of
  Ze's own cognition. This would also require adding a license table entry,
  which the Constitution's closed-enum rule reserves for governing-doctrine
  changes, not a single feature's convenience.
- *Skip the collision detector integration entirely and only do a client-side
  comparison for FR-010's in-view indicator.* Rejected as the sole mechanism —
  FR-010 explicitly requires the disagreement be observable to Phase 126's
  detector "in addition to" the in-view indicator (spec Clarifications,
  Session 2026-08-25, Q2). The in-view indicator is still implemented as a
  direct comparison at render time (R2) — cheap, synchronous, no dependency
  on the fire-and-forget collision path succeeding — but the collision-log
  side-channel is additionally wired per FR-010's explicit requirement.
- *Widen the skip rule to compare `content` similarity instead of provenance.*
  Rejected — reuses an existing, already-doctrine-owned enum (`Provenance`)
  instead of inventing a new heuristic; keeps the skip rule declarative and
  testable.

## R2. In-view disagreement indicator (FR-010) is not collision-detector-dependent

The snapshot view's "Ze's own ranking would place this differently" indicator
(Clarifications Q2) is computed directly: each time the view is rendered, the
service compares the (possibly overridden) displayed position against a fresh
`PriorityView.rank()`/`rank_subset()` call's unmodified order for the same item.
This is synchronous and always available; it does not depend on the
fire-and-forget collision check (R1) succeeding, matching `ze_collision`'s design
intent that the collision log is a best-effort observability signal, never a
blocking or correctness-critical path (`detect.py` module docstring: "Never
blocks, delays, or resolves either write").

## R3. Anchor-relative position representation

Per spec Clarifications (Session 2026-08-26, Q1), a requested position is
expressed relative to another named item, not an absolute index. Concretely: a
`PriorityOverride` row stores `anchor_source_kind` + `anchor_source_id`
(identifying the reference item) and `relation: Literal["above", "below"]`. The
Contribution's `content` field is a human-readable rendering of this (e.g.
"Loop 'Berlin move' requested above Goal 'Quarterly report'") for the NLI
contradiction check in R1 to compare against. `Contribution.entity_ids` is left
empty for these contributions (see R4) — the anchor relation itself, not
`entity_ids` overlap, is scoped per-item by content of the two contributions.

## R4. Scoping the collision candidate match to the same item

`_find_candidates()` (`detect.py:68-77`) falls back to a `target_face`-only match
when neither candidate has `entity_ids` set. Since every reprioritization pair
in R1 shares `target_face=ACTIVE_CONCERNS`, leaving `entity_ids` empty would let
the candidate scan pair a user's override for item A against a stale synthesized
claim about unrelated item B within the same 24-hour window, relying on the NLI
model alone to say "not contradictory" for cross-item noise — fragile and wastes
NLI calls. **Decision**: set `entity_ids=[item.source_id]` (the loop/goal/
hypothesis's own UUID) on both the user's override contribution and its
companion synthesized-claim contribution. `CollisionCandidate.entity_ids` is a
bare `list[UUID]` with no existence check in the collision path (unlike
`evidence` refs, which are existence-checked in `validate_and_submit`), so this
is a safe, minimal reuse: it scopes the candidate match to the same target item
without requiring the item to be a `ze-memory` graph entity.

## R5. Storage ownership and migration

No package in the current migration-ownership table (`CLAUDE.md`) owns tables
for `ze-priority` — it is purely a read/scoring package today (per the codebase
survey: `view.py`, `scoring.py`, `types.py`, `arbitration.py`, no `store.py`).
This feature is the first to give `ze-priority` durable state. **Decision**: add
a new migration chain owned by `ze-priority`, prefix `zpri`, following the same
pattern as `ze-worldstate` (`zw`) and `ze-skills` (`zsk`) — a non-plugin core
package with an explicit `_ZE_PRIORITY_VERSIONS` constant added to
`ze_api/migrate.py` (per CLAUDE.md's "Rules" for non-plugin core packages).
Single new table: `priority_overrides` (see data-model.md).

## R6. Decay function and default window

Spec Assumptions leave the decay window as a planning-time value. **Decision**:
linear decay of override "weight" from `1.0` at submission to `0.0` at
`submitted_at + 48h`, recomputed on each view render (R2, and per Clarifications
Session 2026-08-26 Q3 — no live-update channel). 48 hours is chosen to span a
weekend/short gap without needing daily reaffirmation, consistent with the
existing precedent of `ze_correlation`'s `DEFAULT_DECAY_WINDOW_DAYS` being a
similarly hand-picked, documented constant rather than a user-configurable
setting. The weight blends the override's requested adjacency into
`PriorityView`'s unmodified order (full weight = item placed exactly at the
requested anchor position; weight fading to 0 = item's displayed position
converges back to its unmodified rank). Pinned overrides (FR-009) hold weight at
`1.0` indefinitely.

## R7. Cross-item conflict resolution algorithm (FR-014)

Active overrides (decaying or pinned) are fetched sorted by `submitted_at`
ascending and applied to `PriorityView`'s unmodified order **in that order**: each
override repositions its item adjacent to its anchor at application time. Because
later overrides are applied after earlier ones, a later override's placement
always wins for any pair of items whose requested positions contradict —
satisfying "most-recent-instruction-wins" (Clarifications Session 2026-08-26 Q2)
without a separate conflict-detection pass. An override whose anchor item is no
longer present in `PriorityView`'s current ranking (closed/completed/dropped, or
never resolvable) is skipped entirely for that render (FR-011).

## R8. Conversational path: core tool, not a plugin tool

Per the spec's Assumptions (mechanism is a planning-time decision, weighing that
"core tools are a higher-trust, higher-blast-radius surface than plugin tools,
consistent with FR-007's confirmation requirement"). **Decision**: a new
`reprioritize_item` tool lives in `ze_priority/tools.py` (core package, not a
plugin), registered with `Mode.CONFIRM` capability so `capability_check` routes
it through the existing `draft_response → await_confirmation` LangGraph pause
(`core/ze-core/ze_core/orchestration/nodes/execution.py`) exactly like any other
consequential agent action — no new confirmation primitive is built (FR-007).
This is justified because the action writes a `Contribution` to shared
world-state (`ACTIVE_CONCERNS`), the same trust tier as other core-tool writes
(e.g. `OpenLoop` confirm/close/drop), and because keeping it in `ze-priority`
(the package that owns `PriorityView` and the new `priority_overrides` table)
avoids a plugin depending on core internals to disambiguate and rank items —
disambiguation (FR-006) needs direct access to `PriorityView.rank()`'s live
output, which is a core-package call.

## R9. Frontend: drag-and-drop library

No drag-and-drop library exists in `apps/ze-web` today (`@xyflow/react` is
node/edge diagramming, not list reordering). **Decision**: add `@dnd-kit/core` +
`@dnd-kit/sortable` — the current standard for accessible, keyboard-operable
sortable lists in React, and the natural fit for a single ranked list (as
opposed to `@xyflow/react`'s canvas model). This is a new dependency addition,
not reuse of an existing pattern; flagged here per Technical Context.

## R10. REST + FSD placement

Follows the `collisions.py` route (`apps/ze-api/ze_api/api/routes/collisions.py`)
and Goal Dashboard entity/widget pattern exactly:
- `apps/ze-api/ze_api/api/routes/priority.py` — thin FastAPI router delegating to
  a new `ze_priority.rest` module (`response_model`, `operation_id`, `summary`,
  `description` on every route, per Constitution IV / CLAUDE.md OpenAPI rule).
- `apps/ze-web/src/entities/priority-item/api/usePrioritySnapshotQuery.ts` +
  `useReprioritizeMutation.ts` — React Query hooks over the generated
  `@ze/client` SDK methods.
- `apps/ze-web/src/widgets/priority-snapshot/ui/PrioritySnapshot.tsx` — the
  drag-enabled list widget, consuming the entity hooks.
