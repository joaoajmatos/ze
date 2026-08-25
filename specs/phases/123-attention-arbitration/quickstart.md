# Quickstart: Validating Attention Arbitration

Prerequisites: `make db-up && make migrate` (no new migration for this feature, but
the existing `open_loops`, goal, hypothesis, and `push_log` tables must exist).

## Validate User Story 1 — one ranked list across all three sources

1. Seed one drifting `OpenLoop`, one goal with a `StuckGoal` entry (via
   `GoalStore.list_stuck`), and one `Hypothesis` with confidence 0.4 created
   ~3 days ago (see `contracts/priority_view.md` for the exact store calls; a
   pytest fixture using `AsyncMock` stores is sufficient — no real DB required for
   this check).
2. Run:
   ```python
   ranking = await PriorityView(loop_store, goal_store, hypothesis_store).rank()
   ```
3. Expected: `len(ranking.items) == 3`, each `PriorityItem.source_kind` distinct,
   each carrying a `priority: Confidence` and a `signal` matching its source's
   original value (spot-check `signal.confidence`/`signal.idle_days` against the
   seeded input — nothing should be recomputed, only wrapped).
4. Seed a second scenario: a loop drifting 10 days vs. a hypothesis 1 hour old with
   low confidence. Assert the loop ranks first (`ranking.items[0].source_kind ==
   "loop"`).

## Validate User Story 2 — arbitrated surfacing under shared budget pressure

1. Seed one push-eligible drifting loop (higher priority) and one push-eligible
   hypothesis (lower priority). Configure `max_pushes_per_day=1` and pre-populate
   `push_log` with 0 sends today (one slot remaining).
2. Run `AttentionArbitrationJob.run()`.
3. Expected: exactly one `try_claim_shared` call succeeds (for the loop); the
   hypothesis's candidacy is logged as budget-arbitrated, not silently dropped —
   assert on the log record / a returned outcome list, per how task-breakdown
   decides to surface it (not fixed by this spec beyond "not silently dropped").
4. Repeat with `max_pushes_per_day=0` (or budget already exhausted): assert neither
   candidate is claimed, regardless of rank.

## Validate User Story 3 — one shared budget, not two independent ones

1. Configure `proactive.budget.max_pushes_per_day=3`. Exhaust it via three
   `try_claim_shared(push_log, "hypothesis", ...)` calls (simulating
   correlation-only pushes).
2. Attempt a fourth claim with `source_kind="loop"` later the same day.
3. Expected: the fourth claim returns `False` — withheld by the shared budget, not
   evaluated against a separate worldstate-only counter (there no longer is one).

## Validate degradation (Edge Cases)

1. Configure the mock `HypothesisStore` to raise on its list call.
2. Run `PriorityView.rank()`.
3. Expected: no exception propagates; `ranking.sources_failed == {"hypothesis"}`;
   `ranking.items` still contains the loop/goal items that did succeed.

## Running the real test suite

```bash
make test-priority      # new package's own tests (mocked stores, no real DB)
make test-proactive     # covers the relocated attention_budget module
make test-correlation   # push.py changes
make test-worldstate    # surfacing.py + removed push_sweep.py changes
make lint
```
