# Phase 0 Research: Open-Loop Drift Detection & Surfacing

All five Clarifications were resolved in the spec session; this document resolves the
remaining implementation-shaped unknowns the spec deliberately left open (drift-window
storage, contradiction wiring, push-bar reuse mechanics, inline-node wiring, cooldown storage).

## 1. Where does a loop's "implied timeframe" come from?

**Decision**: Add an optional `implied_window_days: int | None` field to the extraction gate's
JSON response schema (`ze_worldstate/extraction.py`'s `_SYSTEM_PROMPT` and
`_ExtractionGateResult`), and a `drift_deadline: datetime | None` column on `open_loops`,
computed once — at the `suspected → active` (or direct-declared-active) transition — as
`confirmed_at + timedelta(days=implied_window_days or DEFAULT_DRIFT_WINDOW_DAYS)`.

**Rationale**: Phase A's `OpenLoop` has no timeframe concept at all; FR-001 requires one to
exist for drift eligibility to be computable, and the spec's own Clarification pins the default
at 7 days. Computing the deadline once at confirmation time (rather than re-deriving it on every
sweep from loop metadata) keeps the sweep query a simple indexed comparison
(`WHERE state = 'active' AND drift_deadline <= now()`) and matches Phase A's precedent of doing
one-time, confirm-time work (`review.confirm_loop` already exists as the natural hook point).

**Alternatives considered**:
- *Store only a duration, recompute deadline per sweep* — rejected: pushes redundant arithmetic
  into every sweep run for no benefit, and complicates the "no new evidence" check (below),
  which also wants a fixed anchor timestamp.
- *Require the LLM to always emit an explicit deadline date* — rejected: over-specifies model
  output for a benefit (calendar-anchored dates) the feature doesn't need; a day-count relative
  to confirmation is sufficient and simpler to validate/clamp server-side.

## 2. What counts as "no new corroborating evidence" for the sweep?

**Decision**: `link_evidence` (in `LoopStore`) is extended to also bump the loop's `updated_at`
(it currently only inserts the `memory_relationships` row). A loop is drift-sweep-eligible when
`state = 'active' AND drift_deadline <= now() AND updated_at <= confirmed_at` — i.e. nothing has
touched the loop (no new evidence link) since it became active. `list_drift_candidates()` on
`LoopStore` encodes this as one query.

**Rationale**: Reuses the column that already exists and is already updated as part of the
natural evidence-linking write path (`_link_evidence_and_entities` in `extraction.py`, already
called on every re-implication match). No new "last evidence at" column needed.

**Alternatives considered**:
- *New `last_evidence_at` column, set explicitly on link* — rejected: functionally identical to
  reusing `updated_at`, but a second column doing the same job the existing one could do is
  needless schema surface.

## 3. How does the immediate contradiction path (FR-002) plug in?

**Decision**: Extend `ze_worldstate/decay.py::cascade_from_evidence` (already the single
synchronous call site wired to `memory_consolidator.contradiction_hook` in
`ze_api/container.py`) — after computing `new_confidence` for each affected loop, if
`loop.state == LoopState.ACTIVE`, call `loop_store.transition(loop.id, LoopState.DRIFTING)` and
write a rationale via the new `drift.py::compose_contradiction_rationale(evidence_type,
evidence_id)` helper, before returning the updated loop list.

**Rationale**: `cascade_from_evidence` is already *the* write-time contradiction path FR-002
names explicitly — it already receives `loop_store`, already iterates exactly the affected
loops, and Phase A's `_ALLOWED_TRANSITIONS` matrix already permits `ACTIVE → CLOSED/DROPPED` but
not yet `ACTIVE → DRIFTING`; that one transition needs to be added to the matrix in `store.py`
as part of this feature (it was deliberately left out of Phase A's matrix with the comment
"Phase B... not producible here").

**Alternatives considered**:
- *A separate contradiction-listening sweep* — rejected: FR-002 explicitly requires immediacy
  ("without waiting for the next scheduled sweep"); a sweep-based approach cannot satisfy that,
  and `cascade_from_evidence` is already synchronous and already the right call site.

## 4. How is the push bar reused without duplicating it?

**Decision**: Extract four pure/near-pure functions out of `ze_correlation/push.py`'s
`CorrelationPushConsumer` methods, parameterized on primitive values instead of `Hypothesis`:
`passes_confidence(confidence, tau)`, `passes_novelty(summary, recent_summaries, embedder,
max_similarity)`, `passes_grounding(summary, evidence_labels, nli_client, threshold)`,
`within_budget(push_log, event_key, max_per_day, window_hours=24.0)`. `CorrelationPushConsumer`
is refactored to call these same functions (behavior-preserving — same thresholds, same control
flow) so there is exactly one implementation of each bar. `ze_worldstate/surfacing.py`'s new
`LoopSurfacer.passes_push_bar(loop, rationale)` calls the same four functions with the loop's
own confidence/rationale-as-summary/evidence labels and a distinct `event_key`
(`"worldstate_loop_push"` vs. correlation's `"correlation_push"`), so the sibling budget
(Clarification) falls directly out of `PushLogStore` already being keyed by `event_type` string
— no schema change needed there.

**Rationale**: FR-007 explicitly requires "calling into the correlation engine's existing
push-bar mechanics... rather than defining a second, divergent implementation." Extraction to
free functions is the minimal refactor that satisfies this without forcing `ze-worldstate` to
construct or depend on `Hypothesis`/`CorrelationEngine`/`PostgresHypothesisStore` — only
`ze_correlation.push`'s four new free functions are imported, which is the whole of the new
`ze-worldstate → ze-correlation` dependency edge in practice.

**Alternatives considered**:
- *`LoopSurfacer` wraps a `Hypothesis`-shaped adapter and calls `CorrelationPushConsumer`
  directly* — rejected: `CorrelationPushConsumer` is wired to `CorrelationEngine`/seed-picking
  machinery that has nothing to do with loops; forcing loops through that shape is a worse fit
  than extracting the four bar functions it actually needs.
- *Reimplement the bar locally in `ze-worldstate`* — rejected explicitly by the Clarification.

## 5. How does the inline node get wired without a new package dependency?

**Decision**: Add `ze_core/orchestration/nodes/loop_surfacing.py`, structurally identical to
`nodes/correlation.py`: it reads `engine`-equivalent (`surfacer: Any =
config["configurable"].get("loop_surfacer")`) from the injected configurable dict, returns `{}`
immediately if absent, and otherwise calls `surfacer.inline_candidates(entity_ids)` (a method on
a duck-typed object `ze-api`'s `container.py` constructs from `ze_worldstate.surfacing.
LoopSurfacer` and passes into `config["configurable"]["loop_surfacer"]` at graph-invocation time,
the same way `correlation_engine` is passed today). `graph.py`'s `graph_builder()` adds a
`"surface_loops"` node wired off the same `after_execute_tool` fan-out as `"correlate"` (both
run; LangGraph runs parallel branches from a single conditional edge target list, so
`after_execute_tool` is changed to return both branch names, or — simpler — both nodes are
added as unconditional next-steps in sequence: `execute_tool → correlate → surface_loops →
(route)`, preserving `correlate`'s existing single-successor edge shape and avoiding a
LangGraph fan-out/fan-in restructuring for a first version). Either node can independently
append to `state["components"]` and to `final_response`'s text section without stepping on the
other's update (dict-merge semantics already used by `correlate`).

**Rationale**: `config["configurable"]` injection is the exact mechanism `ze_core` already uses
to reference a domain object (`correlation_engine`) without an import-time dependency — reusing
it for `loop_surfacer` is precisely what the Clarification calls for ("introduces no new
dependency edge"). Sequencing `surface_loops` immediately after `correlate` rather than
true-parallel is a deliberate LangGraph-simplicity choice for v1; both still run on every turn
that reaches `execute_tool`, satisfying "runs alongside... the correlation engine's own inline
node."

**Alternatives considered**:
- *True parallel branches with a fan-in join node* — rejected for v1: LangGraph supports this,
  but it requires reducer-typed state fields for the merge and a new join node, which is more
  graph-shape churn than this feature's scope justifies; sequential-but-independent nodes reading
  disjoint state and appending to shared list/text fields achieve the same decoupling with the
  existing dict-merge update pattern `correlate` already relies on.

## 6. Where does the inline-then-push cooldown (FR-012, Edge Cases §3) live?

**Decision**: Every inline mention writes a row to the existing `push_log` table under a third
distinct event key, `"worldstate_loop_inline"`, via the already-injected `PushLogStore`
(available to `ze-api`'s container the same way it already is for correlation and workflow
failure alerts). The push sweep's `LoopSurfacer.passes_push_bar` adds one more gate —
`not await push_log.was_sent_within_hours(f"worldstate_loop_inline:{loop_id}", cooldown_hours)`
— alongside the four reused bar functions.

**Rationale**: `PushLogStore` already supports arbitrary string `event_type` keys and
per-key-lookup (`was_sent_within_hours`); per-loop granularity is achieved by suffixing the loop
id into the key, exactly the pattern `list_workflow_failures_within_hours` already demonstrates
for `LIKE 'workflow_failure:%'` prefix matching. No new table or store method needed beyond
what Phase A/existing `ze-proactive` already ships.

**Alternatives considered**:
- *A dedicated `loop_surfacing_log` table on the `zw` chain* — rejected: duplicates
  `push_log`'s job for no added capability; the existing table's `payload`/`event_type` shape is
  already general enough.

## 7. How is the push bar's relevance gate computed for loops?

**Decision**: `LoopSurfacer` takes a `RelevanceModel` (`ze_memory.relevance.RelevanceModel`,
already a `ze-worldstate → ze-memory` transitive capability, no new package edge) as a
constructor dependency. `passes_push_bar` resolves the loop's linked entity names (the same
resolution `surfacing.py`'s `inline_candidates` already does for entity-overlap matching) and
scores them the same way `CorrelationEngine._run_proactive`'s relevance prefilter does:
`rset = await relevance_model.build(); score = relevance_model.score(rset, entity_names,
topics=[])`. A fifth free function, `passes_relevance(relevance: float, tau: float) -> bool`, is
extracted from `CorrelationPushConsumer._passes_push_bar`'s inline `hypothesis.relevance <
self._cfg.tau_relevance` check, alongside the other four, so there remains exactly one
implementation of every bar condition (FR-007's actual requirement).

**Rationale**: Reuses the identical scoring mechanism the correlation engine uses for its own
proactive relevance prefilter — same `RelevanceModel`, same `topics=[]` call shape — rather than
inventing a second relevance concept for loops. Computing it in `passes_push_bar` (not at drift
time) matches confidence/grounding, which are also evaluated at push-check time, not drift time.

**Alternatives considered**:
- *Skip relevance for loops, rely on entity-overlap alone* — rejected: entity-overlap is already
  the (looser) inline-surfacing gate (FR-006); the push bar is supposed to be a *higher* bar than
  inline, so reusing the same weak signal for both would collapse that distinction.
