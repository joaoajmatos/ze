# Phase 0 Research: Contribution Collision Detection

## R1: How does the `Contribution` write path actually look today?

**Finding**: `core/contracts/ze-plugin/ze_plugin/contribution.py`'s `Contribution` dataclass carries only
`claim_kind`, `provenance`, `confidence`, `target_face`, `source_function`, `evidence` — no ID, no
content, no entity linkage. `validate_and_submit(contribution, write, ...)` uses `Contribution`
purely to run licensing + evidence-existence checks, then delegates to the caller's `write()`
closure and returns whatever it returns. The `Contribution` object itself is never persisted or
given an identity — it's a validation-time projection of the caller's real domain object (`Signal`,
`OpenLoop`, a dream artifact, a `Hypothesis`, a `PersonSource`).

Six real production call sites exist today (confirmed via `grep -rn "validate_and_submit" core
plugins`, excluding tests):

| Site | File | Producer domain object | Content available | Entity linkage available |
|---|---|---|---|---|
| 1 | `ze_worldstate/extraction.py:161` | `OpenLoop` (new) | `loop.title` | `entity_ids` resolved at line ~196, *before* this call |
| 2 | `ze_worldstate/extraction.py:294` | `OpenLoop` (corroboration) | `loop.title` | `entity_ids` resolved earlier in the same function |
| 3 | `ze_memory/retriever.py:1267` | `Signal` | `signal.title` + `signal.summary` | `signal.entities` (`list[EntityRef]`) directly on the type |
| 4 | `ze_memory/dream/dream_pass.py:516` | dream artifact | `content` param, already passed to the function | none resolved at this call site today |
| 5 | `ze_correlation/engine.py:252` | `Hypothesis` | `hypothesis` has a content-bearing field (relation/claim text) | `hypothesis.evidence` (fact/episode/signal refs, not entity refs directly) |
| 6, 7 | `ze_personal/contacts/consolidator.py:174,199` + `graph/memory_hooks.py:58,81` | `PersonSource` | source name/identity fields | the person/contact `id` itself is the natural entity anchor |

**Decision**: Do not change `validate_and_submit`'s signature or behavior (satisfies FR-001
literally — "without altering that path's existing validation, persistence, or rejection
behavior"). Instead:
1. Add two **optional** fields to `Contribution` — `content: str | None = None`,
   `entity_ids: list[UUID] = field(default_factory=list)` — populated by each `_to_contribution()`
   helper from data the producer already has in hand (per the table above; site 4 and parts of
   site 5 need a one-line addition to pass through data that already exists in scope but wasn't
   previously threaded into `Contribution`).
2. Introduce a new wrapper, `submit_and_detect_collisions()`, in the new `ze-collision` package,
   that calls the unmodified `validate_and_submit()`, then — only after a successful write, fully
   fail-open — runs the collision check. The six call sites import this wrapper instead of
   `validate_and_submit` directly; `validate_and_submit` itself keeps working exactly as before
   for any caller that doesn't opt in (there are none today, but nothing requires opting in).

**Alternatives considered**:
- *Modify `validate_and_submit` in place to always run collision detection.* Rejected: couples
  `ze-plugin` (a lightweight, DB-free doctrine/type package) to a Postgres store and an
  `NLIClient`, contradicting `ze-plugin`'s existing scope (`ZePlugin` ABC, signals — no domain
  knowledge, no DB). Also directly risks FR-001's "without altering."
- *A module-level hook registry `validate_and_submit` calls internally.* Rejected: constitution
  Principle IV forbids module-level mutable globals outside the sanctioned `lru_cache`
  singletons; a settable hook list is exactly that kind of global, and it also makes the choke
  point's behavior depend on load-order/registration timing rather than being explicit at each
  call site.
- *Give `Contribution` a full `id: UUID` and require producers to persist that same ID.* Rejected
  as unnecessarily invasive — it would touch the DB schema of four unrelated packages (`ze-memory`,
  `ze-worldstate`, `ze-correlation`, `ze-personal`) purely to satisfy this feature's logging
  format. The collision log instead records each side as `(producer_kind, domain_id)`, with
  `domain_id` supplied by the caller via a `result_id: Callable[[T], UUID]` argument to
  `submit_and_detect_collisions`, extracted from whatever `write()` already returns.

## R2: Where does entity "sameness" come from, and what does it mean to match on it?

**Finding**: Entity linkage is not a field on the domain objects uniformly — `OpenLoop` links
entities via `loop_store.link_entity(loop_id, entity_id)` into `ze-memory`'s
`memory_relationships`/`GraphStore` (a graph edge, not a column), resolved from free text via
`_resolve_entities()` *before* the loop write in `extraction.py`. `Signal` carries
`entities: list[EntityRef]` directly. Both ultimately resolve to canonical IDs in `ze-memory`'s
`memory_entities` table.

**Decision** (matches the clarification already recorded in spec.md's Clarifications section):
match on exact canonical `memory_entities.id` equality, passed into `Contribution.entity_ids` by
each producer from data it already has resolved (no new entity-resolution step). The known
limitation that upstream entity resolution may not have merged two records for what's really the
same real-world entity is accepted and documented in the spec — out of scope for this feature.

## R3: What NLI mechanism does this reuse, and what does "fail open" look like in practice?

**Finding**: `NLIClient` (`core/contracts/ze-agents/ze_agents/nli.py`, `Protocol`) exposes
`scores(pairs: list[tuple[str, str]]) -> list[dict[str, float] | None]` — a `None` entry per pair
already signals "could not be scored" (the protocol's own built-in fail-open channel).
`ze-correlation`'s existing inline NLI usage (`ze_correlation/push.py`,
`_NOVELTY_LOOKBACK_HOURS = 48.0` constant) is the cited precedent for "hard timeout, silent drop"
discipline and for a bounded, configurable recency-window constant pattern.

**Decision**: Reuse the injected `NLIClient` exactly as `ze-correlation` does — call
`scores([(content_a, content_b)])`, treat `None` or an exception/timeout as "not a collision, skip
silently" (FR-008), never propagate the failure to the write path. Recency window follows the same
pattern as `_NOVELTY_LOOKBACK_HOURS`: a module-level constant in `ze_collision/detect.py`
(`_COLLISION_WINDOW_HOURS`), exact value a planning-time default (24h, adjustable later — matches
the spec's Assumptions section framing this as "not fixed by this spec").

## R4: Where does the collision log live, and how is it queried?

**Finding**: `ze-proactive`'s `PushLogStore` (`core/contracts/ze-proactive/ze_proactive/push_log_store.py`,
migrations `zpro001`/`zpro003`) is the cited precedent for "new, small, append-only store." No
existing package currently owns a table for cross-function conflict records. Existing non-plugin
core packages (`ze-worldstate`, `ze-skills`, `ze-correlation`) each own their own migration chain
and are wired directly into `apps/ze-api/ze_api/container.py` and `migrate.py`'s
`_ZE_*_VERSIONS` constants — not folded into `ze-core`.

**Decision**: New package `core/seam/ze-collision`, migration prefix `zcol`, one table
(`contribution_collisions`), following `PushLogStore`'s shape (append-only, no updates, indexed
for the query patterns FR-009 requires). REST surface: `GET /api/v0/collisions` in
`apps/ze-api/ze_api/api/routes/collisions.py`, following the existing `/api/v0/loops`,
`/api/v0/notifications`, `/api/v0/skills` pattern (per the clarification recorded in spec.md).

## R5: Supersession vs. cross-function collision

**Finding**: The spec's edge-case note ("a claim being legitimately updated by its own producing
function... is not a collision") is already structurally guaranteed by FR-002's "different
`source_function`" requirement — a same-function revision never even becomes a *candidate* pair,
because the candidate scan only looks at contributions from other source functions. No additional
logic is needed to special-case supersession.

**Decision**: No supersession-detection code required; FR-002's candidate filter already excludes
it by construction. Covered by a test case asserting a same-function pair never reaches the NLI
check (User Story 1, Acceptance Scenario 2).

## Outstanding NEEDS CLARIFICATION

None — all Technical Context fields are resolved above; nothing carries into Phase 1 unresolved.
