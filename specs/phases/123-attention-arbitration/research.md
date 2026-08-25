# Phase 0 Research: Attention Arbitration

## Decision: New core package `ze-priority` hosts both PriorityView and the arbitration job

**Rationale**: `PriorityView` needs read access to `LoopStore` (ze-worldstate),
`GoalStore` (ze-automation), and `HypothesisStore` (ze-correlation) simultaneously.
No existing package depends on all three (`ze-worldstate` currently depends on
`ze-correlation` only; `ze-automation` and `ze-correlation` depend on neither each
other nor `ze-worldstate`). Putting the arbitration sweep job in either
`ze-worldstate` or `ze-correlation` would force that package to newly depend on the
others, which the spec does not license (FR-010: stores stay separate) and which
would invert the intended narrow, one-directional dependencies each mechanism has
today. A new core package sitting above all three — mirroring the existing
`ze-worldstate → ze-correlation` precedent — is the only shape that avoids a cycle.

**Alternatives considered**:
- *Put PriorityView directly in `apps/ze-api`*: rejected — `ze-api` is meant to be a
  composition root (wiring), not where cross-cutting business logic like ranking
  lives; every other cross-cutting substrate (`ze-worldstate`, `ze-correlation`,
  `ze-automation`) is its own core package, and this should follow suit.
- *Add a dependency from `ze-worldstate` to `ze-automation`*: rejected — no other
  driver for that dependency exists; it would exist solely to serve this feature and
  would need to be reversed or duplicated the day `ze-correlation` also needs goal
  data.

## Decision: One shared `AttentionArbitrationJob` replaces the two independent sweep jobs

**Rationale**: FR-007's "push the higher-ranked item, never both" cannot be
satisfied by two jobs that each independently decide to push — by the time either
job acts, it does not know what the other found. The clarification (2026-08-25,
"greedy real-time check") resolves *when* to check, not *who* checks. Since only
`ze-priority` can see all three sources at once, the check must happen there: one
job pulls push-eligible candidates from both mechanisms (via new eligibility-only
methods described below, which stop short of actually sending), ranks them with
`PriorityView`, and attempts the shared-budget claim for the single top-ranked
candidate. `ze_worldstate.jobs.push_sweep.PushSweepJob` and `ze-correlation`'s
existing autonomous push-trigger path are retired; their per-mechanism *eligibility*
logic (novelty checks, relevance bar, idempotency — SC-004) is preserved unchanged,
just no longer self-triggering a send.

**Alternatives considered**:
- *Keep both jobs, have each query `PriorityView` before pushing (as in the
  clarification's literal wording)*: this is functionally identical to the chosen
  design but would require both `ze-worldstate` and `ze-correlation` to depend on
  `ze-priority` — which already depends on both of them, producing a cycle. Hoisting
  the *call site* (not the eligibility logic) up into `ze-priority` avoids this
  while preserving the same greedy real-time semantics from the user's point of
  view.
- *Batch rendezvous / reservation window*: rejected by the clarification answer
  itself (adds a coordination primitive and push latency the spec doesn't ask for).

## Decision: Goal urgency signal = existing `idle_days` staleness, not gate-deadline proximity

**Rationale**: `core/ze-automation` has no deadline field anywhere in `Goal`,
`Milestone`, or `VerificationGate` (confirmed by exhaustive grep — zero occurrences
of "deadline"). The only existing goal urgency signal exposed by `GoalStore` is
`list_stuck(idle_days, alert_cooldown_days) -> list[StuckGoal]`, where `idle_days`
is time-since-last-progress (last milestone `completed_at`, or gate `fired_at` for
awaiting-gate goals). The spec's acceptance-scenario wording ("a goal milestone 1
day from its gate deadline") describes a deadline-countdown signal that does not
exist in the codebase today. Per FR-003 (must not recompute what a source already
exposes) and the spec's own Assumptions (exact weighting formula is a planning-time
detail), `PriorityView` maps a `StuckGoal`'s `idle_days` to urgency directly — more
idle days since last progress → higher urgency — rather than inventing a
gate-deadline concept `ze-automation` does not have. This is the same "already
computed, don't recompute" posture applied to loops (drift state) and hypotheses
(decay-window staleness).

**Alternatives considered**:
- *Add a deadline field to `Goal`/`Milestone`/`VerificationGate`*: rejected — out of
  scope (this feature is a projection, not a producer-side data model change) and
  would itself need its own spec/clarification about who sets deadlines and how.

## Decision: Shared budget primitive relocates to `core/ze-proactive`

**Rationale**: FR-006 requires the shared attention-budget check to live in
`core/ze-proactive`. Today `within_budget()` and the `_PUSH_LOG_KEY` constant are
defined in `ze_correlation/push.py`, and `ze_worldstate/surfacing.py` imports
`within_budget` *from `ze_correlation`* — an existing cross-package reach-around
that predates this feature. Moving `within_budget()` (plus new
`try_claim_shared()`/`release_shared()` wrappers around `PushLogStore.try_claim` /
`.release_claim`) into `ze_proactive/attention_budget.py` both satisfies FR-006 and
removes `ze_worldstate`'s indirect dependency on `ze_correlation` for this one
primitive (it keeps its direct dependency on `ze_correlation`'s `HypothesisStore`
access, which is unaffected). `ze_correlation/push.py` is updated to import from
`ze_proactive` instead of defining the primitive itself.

## Decision: Single shared push_log event key `attention_push`

**Rationale**: FR-005's Key Entities section calls for "one shared event key"
replacing the two mechanism-specific ones (`correlation_push`,
`worldstate_loop_push`). Idempotency is preserved by namespacing the
`idempotency_key` per claim as `f"{source}:{item_id}"` (e.g.
`"loop:<uuid>"`/`"hypothesis:<uuid>"`), since `PushLogStore.try_claim`'s uniqueness
is `(event_type, idempotency_key)` — a single shared `event_type` with
source-prefixed keys prevents an accidental collision between a loop and a
hypothesis that happen to share a UUID space (they don't today, but the prefix
costs nothing and documents intent).

## Decision: Shared config key `proactive.budget.max_pushes_per_day`

**Rationale**: `core/ze-proactive` has no dedicated settings dataclass — other
proactive jobs read their config ad hoc from `settings.config["proactive"][...]`
(`ze_proactive/bootstrap.py`). Following that established pattern, the new shared
limit reads from `proactive.budget.max_pushes_per_day` in
`apps/ze-api/config/config.yaml`. Per the clarification, its migrated value is the
minimum of the two prior effective values: `correlation.push.max_pushes_per_day`
(3) and `worldstate.push.budget.max_pushes_per_day` (3) → migrated value **3**. The
now-dead keys (`correlation.push.max_pushes_per_day`,
`correlation.salience.budget.max_pushes_per_day`,
`worldstate.push.budget.max_pushes_per_day`) are removed from `config.yaml`
entirely — the spec's Assumptions explicitly say preserving old keys as dead config
is not required.

## Decision: Confidence-based scoring — per-source adapters + deterministic tie-break

**Rationale**: FR-002 requires a priority score computed from the shared
`Confidence` type (`ze_agents.claims`), not a per-source ad hoc score, while FR-003
forbids recomputing each source's underlying signal. The resolution is a thin
per-source *adapter* (not a recomputation) that wraps each mechanism's already-
computed value into a `Confidence`:
- Loops: `OpenLoop.confidence` (already a `float`) wrapped directly, with
  `DecayProfile.TIME_LINEAR` reflecting drift's already-elapsed-time semantics.
  `LoopState.DRIFTING` items are boosted relative to `ACTIVE` (drift is itself a
  signal ze-worldstate already computed, not something PriorityView recomputes —
  it's read off `OpenLoop.state`).
- Goals: `StuckGoal.idle_days` normalized into `Confidence.value` via the existing
  `ze_agents.claims.decay()` helper with `DecayProfile.TIME_LINEAR` and
  `elapsed_days=idle_days` — reusing the shared decay function rather than inventing
  a new normalization curve.
- Hypotheses: `Hypothesis.confidence` (already a `float`, LLM self-rating) combined
  with `Hypothesis.relevance`, wrapped with `DecayProfile.EVIDENCE_WEIGHTED`
  (matches how the existing decay job already characterizes hypothesis confidence
  decay).
Final ranking sorts by `Confidence.value` descending. Ties are broken
deterministically (per the spec's edge case) by each item's own most recent
activity timestamp (loop `updated_at`, goal `StuckGoal`'s reference timestamp,
hypothesis `created_at`) descending, then by a stable UUID comparison as a final
tie-break — guaranteeing the same ranking on repeated queries against unchanged
data.

**Alternatives considered**:
- *Simple weighted sum of raw floats without going through `Confidence`*: rejected
  — fails FR-002's explicit requirement that the resolved score be
  `Confidence`-typed, and would make `PriorityView`'s output shape unusable as a
  `Priority`-kind claim per FR-004.

## Resolved Technical Context unknowns

All Technical Context fields in `plan.md` are fully resolved from the existing
codebase — no `NEEDS CLARIFICATION` markers remain:

- Language/Version, Testing, Storage, Target Platform: inherited from repo-wide
  conventions (`CLAUDE.md`), no feature-specific deviation.
- `ClaimKind.PRIORITY` already exists in `ze_agents/claims.py` — no enum change
  needed; the spec's "first real Priority-kind claim" refers to first *usage*, not a
  missing enum member.
