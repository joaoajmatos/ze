# Attention Arbitration — One Ranked View, One Attention Budget

> **Status:** Proposed (design-only — not yet specced for implementation)
> **Scope:** `core/ze-worldstate`, `ze-automation` (goals), `core/ze-correlation`,
> `core/ze-proactive` (shared push infrastructure).
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
   (`core/ze-correlation/ze_correlation/push.py`) are genuinely reused by
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

- [ ] **Ranking formula** — is priority a weighted combination of confidence × urgency
  (drift proximity / gate deadline / hypothesis novelty), or does each mechanism supply its own
  pre-ranked local order and `PriorityView` only interleaves them? The former is more honest to
  "one function," the latter is cheaper and lower-risk to ship first.
- [ ] **Where `PriorityView` lives** — `core/ze-worldstate` (already the executive-function
  package) or a new thin package that depends on `ze-worldstate`, `ze-automation`, and
  `ze-correlation` without any of them depending on each other? The latter avoids adding
  `ze-automation`/`ze-correlation` as dependencies of `ze-worldstate` just for a read.
- [ ] **Surfacing consumer** — does the briefing/conversation-turn assembly path start reading
  `PriorityView` directly, replacing today's per-mechanism inline logic, or does it stay a
  backend-only ranking used only to arbitrate the shared budget initially (safer, smaller
  first slice)?
- [ ] **Definition of "shared budget"** — one number per day system-wide, or a budget that
  itself varies by the user's current load (fewer interruptions on a day already full of
  meetings)? Recommend starting with the simple system-wide number; this is exactly the kind of
  refinement that should wait for evidence, not be designed in speculatively.
</content>
