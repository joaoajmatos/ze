# Attention Arbitration — One Ranked View, One Attention Budget

> **Status:** Shipped. Implemented as `specs/phases/123-attention-arbitration/spec.md` —
> `PriorityView` (`core/arbitration/ze-priority`), the shared attention budget (`core/contracts/ze-proactive`), and
> the greedy cross-mechanism push check are all live. Phase 127 (`specs/phases/127-priority-override/spec.md`)
> layered user-directed override on top. Loop/goal store reconciliation was explicitly kept out
> of scope (FR-010) and remains open — see "Open Questions" below.
> **Scope:** `core/cognition/ze-worldstate`, `ze-automation` (goals), `core/cognition/ze-correlation`,
> `core/contracts/ze-proactive` (shared push infrastructure).
> **Constrained by:** `specs/arch/ze-doctrine.md` §The epistemic ontology (`Priority` claim-kind),
> §Belief revision.
> **Depends on:** `specs/arch/claim-topology.md` shipping first — this brief needs the shared
> `Confidence` type to rank claims from different producers on the same scale; ranking loops,
> goals, and hypotheses today would mean comparing three incompatible confidence shapes.
> **Relationship to the doctrine's open questions:** this is the concrete brief for
> `docs/cognitive-architecture.md`'s "executive function's remaining slice" — the half of the
> gap that survived Phases 109–110.

---

## Why these three gaps are one brief

Three items looked separate in isolation but turned out to share a single missing piece —
**one ranked view across everything currently open:**

1. **No cross-concern prioritization.** `OpenLoop` has drift state, goals have milestones and
   gates, `Hypothesis` has confidence — three independent notions of "how much does this
   matter right now," never compared. The doctrine names this explicitly: `Priority` is a
   licensed claim-kind (`ze-doctrine.md` §The epistemic ontology — "a judgment about what
   deserves attention now... recomputed continuously as state changes"), and nothing in the
   codebase produces it.
2. **No loop/goal query surface.** `specs/phases/110-open-loop-drift-surfacing/spec.md` (FR-014)
   deliberately left loops and goals unmerged as *stores* — that was the right call, goals carry
   execution machinery (planner, executor, gates) loops don't need. But "deliberately separate
   stores" quietly became "no way to ask 'what's open right now' across both," which is a
   different and unintended cost.
3. **No shared attention budget.** `ze-correlation`'s push mechanics
   (`core/cognition/ze-correlation/ze_correlation/push.py`) are genuinely reused by
   `ze-worldstate`'s `push_sweep.py` — but Phase 110 tracks its own daily push counter as a
   *sibling* to correlation's, against the same `push_log`, rather than one counter both draw
   from. Two mechanisms independently deciding "have I used my interruption budget today"
   against a shared log, without knowing about each other's spend, is how a user ends up
   interrupted twice in one morning by two subsystems that each individually stayed under
   budget.

Once there is one ranked view spanning loops + goals + hypotheses, #3 is almost free: the same
view that ranks *what* to surface is the natural place to enforce *how often*, as a single
budget rather than N independent ones.

---

## What ships (sketch — not yet a spec)

### 1. A `PriorityView` — a read-only projection, not a new store

Consistent with the doctrine's hard constraint that any executive-layer artifact must be a
**projection of the world-state**, not a parallel structure: this is a query, not a table. It
reads `OpenLoop` (via `LoopStore`), goals (via `GoalStore`), and `Hypothesis` (via
`HypothesisStore`), and produces a ranked list using the shared `Confidence` from
`claim-topology.md` plus mechanism-specific signals already computed today (drift state,
milestone/gate proximity, hypothesis novelty) — it does not recompute what each mechanism
already knows, it combines what they already expose.

### 2. `Priority` becomes a real claim-kind, produced by this view

Per the doctrine's licensing table, only the executive function may produce `Priority` claims.
`PriorityView`'s output — "this drifting loop outranks that stale goal milestone right now" —
*is* the executive function's first real `Priority`-kind contribution, and (once
`contribution-seam.md`'s type work has landed) is naturally expressed as a `Contribution` with
`claim_kind=PRIORITY`.

### 3. One attention budget, shared by correlation and worldstate

Move the push-bar budget check itself (not just the push-bar *mechanics*, already shared) into
`ze-proactive`'s `PushLogStore`-adjacent layer, so both `ze-correlation` and `ze-worldstate`
call the same "do I still have interruption budget today" check instead of maintaining sibling
counters. `PriorityView`'s ranking is what arbitrates *which* mechanism gets to spend that
shared budget when both have something drift-worthy on the same day.

---

## What this explicitly does not do

- **Does not merge the `OpenLoop` and goal stores.** FR-014's reasoning stands; this adds a
  read-side view, not a write-side merge.
- **Does not change how loops or goals are individually surfaced today** (inline mentions,
  push-bar gating) — it changes *which one wins* when both want the same interruption slot, and
  gives the user a single "what's open" read surface that doesn't exist today.
- **Does not require the full contribution seam.** `PriorityView` can ship reading directly from
  the three existing stores; expressing its output as a formal `Contribution` is a nice-to-have
  once that type exists, not a blocker.

---

## Open Questions

- [x] **Ranking formula** — resolved per Phase 123 FR-002: a resolved priority score computed
  from the shared `Confidence` type combined with each mechanism's own signal (drift state for
  loops, idle days for goals, novelty/confidence for hypotheses) — not a bare interleave of
  pre-ranked local orders.
- [x] **Where `PriorityView` lives** — resolved as the "new thin package" option: `core/arbitration/ze-priority`,
  depending on `ze-worldstate`, `ze-automation`, and `ze-correlation` (plus `ze-agents`,
  `ze-proactive`, `ze-plugin`, `ze-collision`) without any of those three depending on each
  other, per the dependency graph in the repo's `CLAUDE.md`.
- [ ] **Surfacing consumer** — Phase 123 shipped `PriorityView` as the arbiter for the shared
  push budget (backend-only ranking, per FR-007); Phase 127 added a user-facing snapshot view
  and drag-reorder UI on top. Whether the briefing/conversation-turn assembly path itself reads
  `PriorityView` directly, replacing per-mechanism inline logic there too, remains open.
- [x] **Definition of "shared budget"** — resolved as the simple system-wide number per Phase
  123 FR-005: the single migrated limit is the minimum of the two prior per-mechanism
  `max_pushes_per_day` values, not a load-varying budget.
</content>
