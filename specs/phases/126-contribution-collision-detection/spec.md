# Feature Specification: Contribution Collision Detection

**Feature Branch**: `126-contribution-collision-detection`

**Created**: 2026-08-25

**Status**: Implemented

**Input**: User description: "Instrument Phase 124's validated Contribution write path to detect, log, and surface — but not resolve — cases where two contributions from different source_functions target overlapping world-state (same linked entity or same target_face) with conflicting content, so we have concrete evidence of the trigger condition specs/arch/contribution-seam.md's step 5 (real cross-contribution arbitration) is gated on, instead of guessing at requirements for arbitration before any real collision has been observed. This is detection and logging only — when a collision is flagged, both contributions are still persisted via their normal write paths exactly as today (no contribution is blocked, delayed, or auto-resolved); the doctrine's existing per-function arbitration order and each store's existing contradiction handling (e.g. ze-memory's NLI-based fact contradiction detection) continue operating unchanged. A collision is defined narrowly: two contributions from different source_functions, submitted within a bounded recency window, that link to the same entity (or, absent shared entity linkage, target the same target_face) and whose content an NLI contradiction check flags as conflicting — not merely two contributions that happen to co-occur or overlap thematically. Log entries are queryable so that, after enough real collisions accumulate (or a single high-stakes one), there is concrete evidence to decide whether to spec real arbitration, rather than the current state of zero visibility into whether the trigger condition has ever fired."

**Governed by**: [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md) (constitutional —
§Arbitration: "when subsystems disagree... something must arbitrate" — this feature detects
disagreement, it does not arbitrate it), and
[`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md) (phased-rollout step 5's
own trigger condition — "only once two functions demonstrably collide" — which this feature
exists to make observable). Depends on
[`specs/phases/124-contribution-seam-core/spec.md`](../124-contribution-seam-core/spec.md) (the
`Contribution` type and validated write path this feature observes) and, transitively,
[`specs/arch/claim-topology.md`](../../arch/claim-topology.md) / Phase 111. Does not build real
cross-contribution arbitration — that remains explicitly out of scope until this feature's own
evidence justifies specing it.

---

## Clarifications

### Session 2026-08-26

- Q: What interface should FR-009's query surface use? → A: A REST endpoint (e.g.
  `GET /api/v0/...`), following the codebase's existing pattern for every other queryable store
  (loops, notifications, skills).
- Q: For entity matching in the collision check, given that upstream entity resolution (merging
  duplicate entity records for the same real-world thing) is a separate, already-existing system
  this feature doesn't touch, how should this feature handle imperfect upstream resolution? → A:
  Match only on identical canonical entity IDs as already linked by producers (no new
  resolution/dedup step); if upstream entity resolution hasn't merged two records that represent
  the same real-world entity, this feature will not catch that collision. This is an explicitly
  flagged, accepted limitation — not a defect of this feature — and is a candidate for a future
  spec if evidence shows it matters.

## Overview

`contribution-seam.md`'s phased rollout gates real arbitration (step 5) on a trigger condition —
"two functions demonstrably collide on the same world-state face" — but nothing in the system
today would tell anyone if that trigger had actually fired. The doctrine's own precedence order
(governance > user-stated > fact > inference > suspicion) exists on paper for exactly this
situation, but is currently untested against any real case, because no mechanism observes
whether two contributions from different cognitive functions ever land on the same claim in
conflict with each other.

This feature closes that visibility gap without building the thing it's gathering evidence for.
It hooks Phase 124's validated `Contribution` write path — the single choke point every
retrofitted producer (`Signal`, `OpenLoop`, dream, correlation, and later contacts/action per
Phase 125) already passes through — to check each newly-submitted contribution against
recently-submitted contributions from *other* source functions that plausibly target the same
piece of world-state. When two such contributions conflict in content (not merely co-occur), the
collision is logged with enough detail to review later. Nothing is blocked, delayed, or
auto-resolved: both contributions are persisted through their normal paths exactly as they would
be without this feature. The only new behavior is a queryable record of "this happened."

This is deliberately the opposite of premature abstraction: rather than guessing what real
arbitration should look like before any collision has been observed, this feature makes the
trigger condition itself observable, so the decision to spec step 5 — if it ever comes — is made
from evidence, not speculation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A real collision gets logged, not silently absorbed (Priority: P1)

As Ze's maintainer, when two different cognitive functions submit contributions that
conflict about the same entity or world-state face, I can find out that it happened — today I
would have no way to know unless a user happened to notice the contradiction themselves.

**Why this priority**: This is the entire point of the feature; without it, there is nothing to
build.

**Independent Test**: Submit a `FACT` contribution from perception linking entity X with content
"X moved to Berlin," then submit an `INFERENCE` contribution from reflection linking the same
entity X with content implying X is still in its prior location, within the recency window.
Assert a collision log entry is created referencing both contributions, and assert both
contributions were still persisted via their normal write paths.

**Acceptance Scenarios**:

1. **Given** two contributions from different `source_function`s linking the same entity within
   the recency window, **When** an NLI contradiction check flags their content as conflicting,
   **Then** a collision log entry is created referencing both contribution IDs, their
   `source_function`s, `claim_kind`s, and the conflicting content, and both contributions are
   persisted exactly as their normal write paths would have persisted them regardless.
2. **Given** two contributions from the *same* `source_function` that conflict (e.g. two
   memory-originated facts), **When** submitted, **Then** no collision log entry is created —
   this is existing intra-function contradiction handling (e.g. `ze-memory`'s NLI-based fact
   contradiction detection), which this feature does not duplicate or interfere with.

---

### User Story 2 - Thematic overlap without real conflict is not logged as a collision (Priority: P1)

As Ze's maintainer, I don't want the collision log flooded with every pair of contributions that
happen to touch the same entity or topic — only genuine content-level conflicts.

**Why this priority**: A noisy log is as useless as no log — this is what makes the detector's
output trustworthy evidence rather than something that has to be manually re-filtered before
it's useful.

**Independent Test**: Submit two contributions from different `source_function`s linking the
same entity with compatible (non-conflicting) content. Assert no collision log entry is created.

**Acceptance Scenarios**:

1. **Given** two contributions from different `source_function`s linking the same entity, with
   content that is merely thematically related but not contradictory, **When** submitted,
   **Then** no collision log entry is created.
2. **Given** two contributions from different `source_function`s targeting the same
   `target_face` but linking no shared entity and having unrelated content, **When** submitted,
   **Then** no collision log entry is created (absent both shared entity linkage and detected
   content conflict, this is not treated as a collision).

---

### User Story 3 - Collision log is queryable for review (Priority: P2)

As Ze's maintainer, I can list logged collisions (filtered by date range, involved functions,
or entity) to decide, after real evidence accumulates, whether real arbitration is worth
speccing.

**Why this priority**: Lower than P1 because logging without any way to review it defeats the
purpose, but it's a straightforward read surface once logging itself works.

**Independent Test**: Log several collisions across different `source_function` pairs and
entities. Query the collision log filtered by a specific entity. Assert only matching entries
are returned, each with enough detail (both contribution summaries, `source_function`s,
`claim_kind`s, detected conflict description, timestamp) to review the case without needing to
separately look up the original contributions.

**Acceptance Scenarios**:

1. **Given** multiple logged collisions, **When** queried filtered by entity or by
   `source_function` pair, **Then** only matching entries are returned with sufficient detail to
   review the collision without further lookups.

---

### Edge Cases

- What happens when the recency window has two contributions from different functions about the
  same entity, but the second is a direct, licensed *supersession* of the first (e.g. a newer
  `FACT` correctly superseding an older one per normal belief revision)? Supersession within the
  same claim's own revision lifecycle is not a collision — the check targets contributions from
  *different* `source_function`s in tension, not a claim being legitimately updated by its own
  producing function or a downstream corroboration step.
- What happens if the NLI contradiction check itself fails or times out for a given pair? Fail
  open on detection (skip logging that pair, do not block either contribution's write) — this
  feature must never become a reason a legitimate write fails, consistent with the correlation
  engine's existing "hard timeout, silent drop" discipline for inline NLI checks.
- What happens when three or more contributions from three different functions all touch the
  same entity within the window, with only two of them actually conflicting? Only the
  genuinely-conflicting pair(s) are logged; the check is pairwise on content conflict, not
  "any group sharing an entity is suspect."
- What happens to collision log volume over time if this feature runs for months with zero real
  collisions? That is itself the expected, useful outcome — an empty or near-empty log after
  meaningful runtime is direct evidence that step 5's trigger has not fired and speccing real
  arbitration remains premature.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST observe every contribution passing through Phase 124's validated
  `Contribution` write path (the single choke point for `Signal`, `OpenLoop`, dream,
  correlation, and any later-retrofitted producer) without altering that path's existing
  validation, persistence, or rejection behavior.
- **FR-002**: For each newly-submitted contribution, system MUST check it against contributions
  submitted within a bounded, configurable recency window from a **different**
  `source_function` that share a linked entity, or — absent shared entity linkage — share the
  same `target_face`.
- **FR-003**: For each such candidate pair, system MUST run an NLI-based content contradiction
  check (reusing the existing `NLIClient` protocol) to determine genuine conflict, not merely
  co-occurrence or thematic overlap.
- **FR-004**: System MUST log a collision entry only when FR-002's targeting condition and
  FR-003's content-conflict condition both hold — logging every co-occurring pair (without the
  content check) is explicitly insufficient.
- **FR-005**: A logged collision entry MUST record both contributions' IDs, `source_function`s,
  `claim_kind`s, the linked entity or `target_face` that triggered the match, a summary of the
  detected conflict, and a timestamp.
- **FR-006**: System MUST NOT block, delay, retry, or auto-resolve either contribution when a
  collision is detected — both are persisted via their existing normal write paths exactly as
  they would be without this feature running.
- **FR-007**: System MUST NOT duplicate or interfere with existing intra-function contradiction
  handling (e.g. `ze-memory`'s NLI-based fact contradiction detection, which already resolves
  conflicts *within* memory's own writes) — this feature only checks pairs from *different*
  `source_function`s.
- **FR-008**: The NLI contradiction check MUST fail open — if it errors or times out for a given
  pair, that pair is skipped (not logged as a collision, not blocked), consistent with existing
  inline-NLI-check discipline elsewhere in the codebase.
- **FR-009**: System MUST provide a query surface over logged collisions, exposed as a REST
  endpoint under `/api/v0/`, filterable at minimum by entity, by `source_function`, and by date
  range — following the existing pattern for other queryable stores (e.g. `GET /api/v0/loops`,
  `/api/v0/notifications`, `/api/v0/skills`).
- **FR-010**: A contribution that legitimately supersedes an earlier claim within its own
  producing function's normal revision lifecycle MUST NOT be logged as a collision against the
  claim it supersedes.
- **FR-011**: This feature MUST NOT implement real cross-contribution arbitration (precedence
  resolution, blocking, or auto-merging) — it is detection and logging only.

### Key Entities

- **Collision log entry**: A record of two conflicting contributions from different
  `source_function`s — contribution IDs, source functions, claim kinds, the matched entity or
  target_face, a conflict summary, and a timestamp. Append-only; not itself a claim on the
  world-state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every genuine cross-function content conflict submitted through the `Contribution`
  write path during testing is logged — zero false negatives in the test suite's seeded
  collision scenarios.
- **SC-002**: Contributions that merely co-occur on the same entity/target_face without content
  conflict produce zero collision log entries across the test suite's seeded non-collision
  scenarios — false-positive rate in tests is zero.
- **SC-003**: Enabling this feature introduces no observable change to existing write-path
  latency budgets or outcomes beyond the added detection check — every existing Phase 124/125
  test continues to pass unchanged, and detection failures never block a write (verified by a
  fault-injection test on the NLI check).
- **SC-004**: After the feature has been running, a maintainer can answer "has the arbitration
  trigger condition ever fired, and if so how many times, involving which functions" from the
  collision log alone, without manual log-diving across per-function stores.

## Assumptions

- "Bounded, configurable recency window" reuses the same kind of window/threshold pattern
  already established by the correlation engine's novelty check
  (`_NOVELTY_LOOKBACK_HOURS`) and worldstate's stale-suspicion sweep — an exact default value is
  a planning-time detail, not fixed by this spec.
- Entity linkage for the "same entity" match reuses each producer's existing entity-linking
  mechanism (e.g. `OpenLoop.link_entity`, `Signal.entities`) rather than introducing a new
  entity-resolution step — this feature is a consumer of existing linkage, not a new one. Match
  is on exact canonical entity ID equality. **Known limitation**: entity *resolution* (merging
  duplicate records that represent the same real-world entity, e.g. two contacts with different
  names/emails later recognized as one person) is a separate, already-existing concern (`ze-personal`
  contact consolidation, `ze-memory` entity resolution) that this feature does not touch. If
  upstream resolution hasn't merged two records for what is actually the same entity, a genuine
  collision between them will not be caught by this feature — accepted as an explicit gap, not
  silently swallowed, and a candidate for a future spec if evidence shows it matters.
- The collision log is a new, small, append-only store (modeled on `ze-proactive`'s
  `PushLogStore` pattern) — not a reuse of `push_log` itself, since collisions are not push
  notifications and conflating the two would make both harder to reason about.
- This feature's home package is `core/ze-plugin`, alongside the `Contribution` write path it
  observes (per `contribution-seam.md`'s own placement of the type and write path there),
  though the exact package is a planning-time decision if a better-fitting location (e.g.
  `ze-core` governance, since arbitration-adjacent concerns are named as governance's domain in
  the doctrine) is identified during `/speckit-plan`.
- Whether or how a logged collision surfaces to the user (a notification, a dashboard) is out of
  scope for this spec — this feature's contract ends at "queryable log," per the user
  description's framing of this as evidence-gathering, not user-facing surfacing.
