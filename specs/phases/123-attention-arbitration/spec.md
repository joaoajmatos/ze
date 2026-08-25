# Feature Specification: Attention Arbitration — PriorityView + Shared Push Budget

**Feature Branch**: `123-attention-arbitration`

**Created**: 2026-08-25

**Status**: Draft

**Input**: User description: "Implement attention-arbitration per specs/arch/attention-arbitration.md: a read-only PriorityView projection over LoopStore (ze-worldstate), GoalStore (ze-automation), and HypothesisStore (ze-correlation) that ranks open loops, goal milestones/gates, and hypotheses on one comparable scale using the shared Confidence type from ze_agents.claims (Phase 111), combining each mechanism's existing locally-computed signals (drift state, milestone/gate proximity, hypothesis novelty) rather than recomputing them. PriorityView's output is the executive function's first real Priority-kind claim per the doctrine's claim-kind licensing table. Also consolidate the two sibling daily push-budget counters currently maintained independently by ze-correlation's push.py and ze-worldstate's push_sweep.py against the same push_log table into one shared attention-budget check, likely living in ze-proactive, so PriorityView's ranking is what arbitrates which mechanism spends the shared interruption budget on a given day. Explicitly out of scope: merging the OpenLoop and goal stores (FR-014's separate-stores decision stands), and the full Contribution-seam arbitration mechanism from contribution-seam.md (no orchestration seam yet, this is a query only)."

**Governed by**: [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md) (constitutional —
§The epistemic ontology's `Priority` claim-kind, §Arbitration), and
[`specs/arch/attention-arbitration.md`](../../arch/attention-arbitration.md) (the design brief
this feature implements). Depends on
[`specs/arch/claim-topology.md`](../../arch/claim-topology.md) / Phase 111 (shipped — the shared
`Confidence`/`ClaimKind` vocabulary this feature ranks claims on). Does not build
[`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md)'s `Contribution` type or
arbitration mechanism — no two functions are yet colliding over the same world-state face, so
that trigger has not fired; this feature is a read-only ranking query only.

---

## Clarifications

### Session 2026-08-25

- Q: Correlation's and worldstate's push sweeps run on independent schedules, not
  simultaneously. How should FR-007's "push the higher-ranked item" arbitration work given they
  don't run at the same moment? → A: Greedy real-time check — each sweep queries `PriorityView`
  over all currently-eligible-and-unpushed items across sources at push time, and only pushes if
  it is the top-ranked one. No new coordination primitive.
- Q: FR-005 replaces two independently-configured `max_pushes_per_day` values with one shared
  limit. What should the new single value be derived from? → A: The minimum of the two existing
  configured values, so post-migration daily interruption volume is never higher than the
  smaller of the two prior limits.
- Q: FR-001 says PriorityView includes "recent hypotheses" but doesn't define a recency cutoff.
  What bounds eligibility? → A: Reuse `HypothesisDecayJob`'s existing staleness definition
  (Phase 111, `ze-correlation`) — any hypothesis that job hasn't yet treated as stale is
  eligible; no new PriorityView-specific threshold.
- Correction (found during `/speckit-plan` research): `ze-automation` has no deadline field
  anywhere in `Goal`, `Milestone`, or `VerificationGate` — a gate-deadline-countdown signal, as
  originally described below in the User Story 1 scenario and SC-003, does not exist in the
  codebase. The goal urgency signal PriorityView actually ranks on is `StuckGoal.idle_days`
  (days since last milestone/gate progress), the only urgency signal `GoalStore` exposes today.
  User Story 1's Independent Test/Acceptance Scenario 1 and SC-003 below are updated to describe
  this signal instead of a gate deadline, per FR-003 (PriorityView must not invent a signal a
  source mechanism doesn't already expose).

## Overview

Three independent mechanisms each already compute "how much does this matter right now" for
their own slice of the world-state — `OpenLoop` drift state (`ze-worldstate`), idle days since a
goal's last milestone/gate progress (`ze-automation`), and hypothesis novelty/confidence
(`ze-correlation`) — but nothing compares them. A user with a drifting loop, a stuck goal gate,
and a fresh correlation hypothesis open at the same time has no way to see, and Ze has no way to
reason about, which of the three actually deserves attention first. The doctrine names this gap
explicitly: `Priority` is a licensed claim-kind ("a judgment about what deserves attention now…
recomputed continuously as state changes"), and today nothing in the codebase produces it.

A second, related gap: `ze-correlation` and `ze-worldstate` each independently track a daily
push-notification budget against the same `push_log` table, via the same shared `within_budget()`
primitive but with different event keys and independently configured `max_pushes_per_day` values.
Two mechanisms that each individually stay under their own budget can still interrupt the user
twice in one morning, because neither knows the other has already spent attention today.

This feature closes both gaps with one read-only projection (no new store, consistent with the
doctrine's constraint that any executive-layer artifact must be a projection of the world-state,
not a parallel structure) plus one shared budget check. It does not change what any of the three
producer mechanisms compute internally — it combines what they already expose.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Seeing one ranked list of what's open (Priority: P1)

As the user, when I ask Ze "what's open right now" (or view the equivalent panel/summary), I get
one list spanning drifting loops, stuck or near-gate goal milestones, and live hypotheses,
ordered by how urgently each deserves my attention — not three separate lists I have to compare
myself.

**Why this priority**: This is the entire point of the feature — without a combined ranking, the
other two user stories have nothing to arbitrate.

**Independent Test**: Seed one drifting `OpenLoop`, one goal stuck for several days since its
last milestone/gate progress, and one recent high-confidence `Hypothesis`. Query `PriorityView`.
Assert the response is a single ordered list containing all three, each tagged with its source
claim-kind and a comparable priority score.

**Acceptance Scenarios**:

1. **Given** a drifting `OpenLoop`, a goal idle for several days since its last milestone/gate
   progress, and a 3-day-old `Hypothesis` with confidence 0.4, **When** `PriorityView` is
   queried, **Then** all three appear in one ordered list, each carrying its source type, its
   underlying confidence/urgency signal, and a resolved rank.
2. **Given** two items with materially different urgency (a loop drifting for 10 days vs. a
   hypothesis generated 1 hour ago with low confidence), **When** ranked, **Then** the more
   urgent item (the long-drifting loop) ranks above the less urgent one.

---

### User Story 2 - Ze surfaces the most-deserving item first, not whichever mechanism ran last (Priority: P2)

As the user, when Ze proactively interrupts me about something open, the item it chooses is the
one `PriorityView` ranks highest across all sources that day — not simply whichever of
correlation's or worldstate's sweep jobs happened to run first and still had budget left.

**Why this priority**: Without this, `PriorityView`'s ranking is informational only and doesn't
actually change behavior — it has to gate which mechanism gets to spend the shared budget.

**Independent Test**: Seed a lower-priority hypothesis and a higher-priority drifting loop on
the same day, with only one shared push remaining in the budget. Run both sweep paths. Assert
only the higher-ranked item (the loop) is pushed, and the hypothesis's push attempt is withheld
for budget reasons, not silently dropped.

**Acceptance Scenarios**:

1. **Given** one remaining push in the shared daily budget, a rankable loop, and a rankable
   hypothesis both otherwise eligible to push, **When** both sweep paths run, **Then** only the
   higher-ranked item is pushed and the outcome is logged as budget-arbitrated for the other.
2. **Given** zero remaining pushes in the shared budget, **When** either sweep path attempts to
   push, **Then** neither pushes, regardless of rank.

---

### User Story 3 - One attention budget, not two independent ones (Priority: P3)

As the user, my daily interruption budget from proactive nudges is one number I can reason
about and configure, not two separately-configured limits that happen to write to the same log.

**Why this priority**: Lower priority than P1/P2 because the sibling-counter problem is a
correctness bug (double interruption), not a missing capability — the ranking (P1/P2) is the
feature; the shared counter is a fix riding along with it.

**Independent Test**: Configure one shared `max_pushes_per_day`. Exhaust it via correlation
pushes alone. Assert a subsequent worldstate push attempt on the same day is also withheld.

**Acceptance Scenarios**:

1. **Given** a shared budget of 3 pushes/day already spent entirely by `ze-correlation`,
   **When** `ze-worldstate`'s push sweep runs later the same day, **Then** it is withheld by the
   shared budget check, not evaluated against its own separate counter.

---

### Edge Cases

- What happens when one of the three source stores (loops, goals, hypotheses) has nothing open?
  `PriorityView` returns a ranking over whichever sources have items — it never errors on an
  empty source.
- How does the system handle a tie in resolved priority across two items from different sources?
  Resolve deterministically (e.g. stable ordering by recency) rather than arbitrarily reordering
  between queries.
- What happens if a source store is unreachable (DB error) when `PriorityView` is queried?
  Degrade to ranking the sources that succeeded; do not fail the whole projection because one
  source errored.
- What happens to the shared budget check if the two mechanisms race (both check "is there
  budget" concurrently before either claims it)? Must not allow both to push when only one slot
  remains — reuse the existing claim-then-notify pattern (`try_claim`/`release_claim`) rather
  than a check-then-act race.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `PriorityView` read-only query that returns a single ranked
  list combining currently-open items from `LoopStore` (`ze-worldstate`), active goal
  milestones/gates (`GoalStore`, `ze-automation`), and recent hypotheses (`HypothesisStore`,
  `ze-correlation`). "Recent" for hypotheses is bounded by `HypothesisDecayJob`'s existing
  staleness definition — any hypothesis that job has not yet marked stale is eligible; PriorityView
  MUST NOT define its own separate recency threshold.
- **FR-002**: Each item in the ranked list MUST carry its source claim-kind, its originating
  mechanism-specific signal (drift state for loops, idle days since last milestone/gate progress
  for goals, novelty/confidence for hypotheses), and a resolved priority score computed from the
  shared `Confidence` type (`ze_agents.claims`, Phase 111) rather than a per-source ad hoc score.
- **FR-003**: `PriorityView` MUST NOT recompute what each source mechanism already exposes (e.g.
  it must not reimplement drift detection or gate-proximity calculation) — it combines existing
  signals, per the doctrine's constraint that executive-layer artifacts are projections, not
  parallel structures.
- **FR-004**: `PriorityView`'s output MUST be expressible as a `Priority`-kind claim per the
  doctrine's claim-kind licensing table (only the executive function may produce `Priority`
  claims) — it is not required to integrate with `contribution-seam.md`'s `Contribution` type
  in this feature, but its shape must not preclude that integration later.
- **FR-005**: System MUST consolidate the two independently-configured daily push budgets
  currently maintained by `ze-correlation`'s `CorrelationPushConsumer` and `ze-worldstate`'s
  `LoopSurfacer`/push sweep (both calling `within_budget()` against the same `push_log` table,
  but with different event keys and separately configured `max_pushes_per_day`) into one shared
  attention-budget check with a single configured limit. The migrated single limit MUST be
  derived as the minimum of the two prior `max_pushes_per_day` values, so post-migration daily
  interruption volume is never higher than the smaller of the two prior limits.
- **FR-006**: The shared attention-budget check MUST live in `core/ze-proactive` (the existing
  home of `PushLogStore` and the shared push-bar primitives), not duplicated per caller.
- **FR-007**: When both `ze-correlation` and `ze-worldstate` have eligible items to push on the
  same day and the shared budget cannot cover both, the system MUST push the item `PriorityView`
  ranks higher, and MUST NOT push both. Because the two sweeps run on independent schedules
  (not simultaneously), this MUST be implemented as a greedy real-time check: at push time, each
  sweep queries `PriorityView` over all currently-eligible-and-unpushed items across both
  sources, and only pushes if it is the top-ranked one among them. No new cross-mechanism
  coordination primitive (batching, reservation windows) is introduced by this feature.
- **FR-008**: The shared budget check MUST use an atomic claim (not check-then-act) to prevent a
  race between the two sweep paths from both pushing when only one slot remains, consistent with
  the existing `try_claim`/`release_claim` idempotency pattern already used by
  `ze-worldstate`'s `LoopSurfacer`.
- **FR-009**: `PriorityView` MUST degrade gracefully if one source store fails to answer —
  ranking continues over the sources that succeeded rather than failing the whole query.
- **FR-010**: System MUST NOT merge the `OpenLoop` and goal stores, and MUST NOT build
  `contribution-seam.md`'s full `Contribution` type or arbitration orchestration seam as part of
  this feature — both are explicitly out of scope.

### Key Entities

- **PriorityView (query result)**: An ordered list of ranked items, each wrapping a reference to
  its source entity (`OpenLoop`, goal milestone/gate, or `Hypothesis`), the source's claim-kind,
  its resolved `Confidence`-based priority score, and the mechanism-specific signal that fed the
  score. Not a persisted entity — computed fresh per query.
- **Shared attention budget**: The single daily push-count ceiling and its current spend,
  tracked in the existing `push_log` table under one shared event key, replacing the two
  sibling per-mechanism counters.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single query returns a fully ranked view across all three sources in under 500ms
  for a typical working set (tens of open loops/goals/hypotheses), with no source mechanism's
  own logic re-executed.
- **SC-002**: On any given day, the user receives at most the configured number of proactive
  attention nudges in total across correlation and worldstate combined — never more, regardless
  of how many separate mechanisms have something eligible to surface.
- **SC-003**: When two mechanisms compete for the last available daily nudge, the one surfaced
  to the user is always the one an independent observer would judge more urgent given the same
  ranking inputs (drift duration, idle days since last goal progress, hypothesis
  novelty/confidence) — not whichever mechanism's sweep job happened to run first.
- **SC-004**: Existing correlation-push and worldstate-push behavior (novelty checks, relevance
  bar, idempotency) continues to function unchanged for any single mechanism running in
  isolation — the shared budget only changes cross-mechanism arbitration, not each mechanism's
  own eligibility bar.

## Assumptions

- `PriorityView` is read-only and has no REST/API surface requirement in this spec beyond
  whatever internal call sites (proactive jobs, an eventual "what's open" summary) need it;
  exposing it via a user-facing endpoint is a follow-on concern, not blocking this feature.
- The priority score's exact weighting formula (how drift duration, goal idle-days, and
  hypothesis novelty/confidence combine into one comparable number) is an implementation detail
  resolved at planning time, not fixed by this spec — the spec's contract is that the three
  signal types feed one shared, comparable `Confidence`-typed score, not the specific formula.
- "One shared limit" for FR-005 replaces both existing `max_pushes_per_day` config values with a
  single value; migrating existing config keys is in scope, but preserving both old keys as
  dead config is not required.
- No new database tables are required — `push_log` already supports the claim/release pattern
  this feature reuses; only a shared event key and shared budget-check call site change.
