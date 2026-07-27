# Aperture Decision — What Ze's Executive Layer Optimises For

> **Status:** Ratified — Option A (open loops first) shipped as `core/ze-worldstate`
> (Phase 109 substrate, Phase 110 drift detection & surfacing).
> **Scope:** `core/ze-worldstate`; downstream: correlation, briefings, proactive surface.
> **Constrained by:** `specs/arch/ze-doctrine.md`. The spine (world-state) is settled; this
> brief decided which **projection** of it the product is built around first.
> **Enables:** the contribution seam (`specs/arch/contribution-seam.md`) now has a second
> real client to extract from — see that document's open question on timing.

---

## Context

The doctrine settled the spine: Ze's continuous core is the **world-state** — the model of
you and your active concerns. It deliberately left one thing open: the **aperture**, the
product's centre of gravity. The live tension is between two framings the owner is torn on
(wants the first, leans toward the second):

- **Open loops** — Ze as a command centre for unfinished business.
- **Life-graph + intervention engine** — build the bounded world-model explicitly and focus
  the product on *when to intervene*.

This brief exists to make that decision tractable, not to force it. Its central claim: these
are **not rival visions**. They are the same trajectory at two time horizons, and the real
decision is narrower and more concrete than "which vision."

---

## What is actually being decided

Not "which vision." Both are projections of the one agreed world-state. The decision reduces
to two concrete, spec-able questions:

1. **What is the first-class unit of the executive layer?** An *open loop* (a lightweight,
   implicitly-opened item of unfinished business) or a *node/edge in a life-graph* (an
   explicit relational model queried for pressure points)?
2. **What is the surfacing discipline?** When and how does the executive layer earn the right
   to change what the user sees or does?

Everything else — storage, extraction, jobs — follows from these two. Pick the unit and the
surfacing discipline, and the phase spec writes itself.

---

## Option A — Open loops first

**The primitive.** An *open loop* is a single item of unfinished business with a lifecycle:

```
opened → active → drifting → closed | dropped
```

Crucially, loops are **opened implicitly by perception**, not declared by the user: a promise
in an email thread, a decision left pending in conversation, a "I should look into X"
mentioned once, a project whose dependency stalled. A **goal is the special case**: an open
loop the user explicitly declared and committed resources to. This makes the doctrine's
"goals are one heavyweight kind of active concern" literally true in the schema.

**What ships (v1 slice):**
- A loop store (the fourth face of the world-state, made concrete).
- Loop extraction — perception proposes loops (email, conversation, calendar, ingestion).
- Drift detection — a loop goes `drifting` when reality diverges from its implied plan.
- A surfacing policy — which loops earn a mention, when, at what interruption cost (reuses
  the correlation engine's inline-vs-push bar asymmetry).

**Pros:** namable, groundable, immediately useful; gives reflection a real consumer (closes
the "reflection overbuilt, consumer underbuilt" gap); every loop has provenance, nothing
speculative; subsumes goals rather than competing with them. Lowest risk of overengineering.

**Cons:** "productivity-shaped"; a flat loop list under-uses the memory graph; risks feeling
like a smarter to-do app before the relational intelligence shows up.

---

## Option B — Life-graph + intervention engine first

**The primitive.** An explicit, bounded relational model (extending the existing memory graph:
entities, events, topics, and their typed relationships within the user's relevance set),
queried by an **intervention engine** that decides when a pattern, tension, or convergence in
the graph is worth surfacing.

**What ships (v1 slice):**
- Graph enrichment so the neighbourhood is dense enough to reason over (already partly built:
  Phases 55–60, correlation engine).
- An intervention engine — generalises the correlation engine from "connections in an answer"
  to "unprompted, well-timed interventions" (this is Phase 59, currently deferred).
- A calibrated interruption bar (the hard, deferred problem).

**Pros:** most aligned with the original "connects things across your life" vision; uses the
graph and correlation investment directly; the intelligence is visible early.

**Cons:** the doctrine flags this as "most technically elegant, easiest to overengineer"; the
interruption-timing problem is genuinely unsolved and is where the system most easily becomes
a spam/conspiracy generator; hard to ground "value" without a concrete unit like a loop.

---

## The reconciliation (why this is sequencing, not either/or)

- **Active concerns *are* open loops.** The doctrine's fourth face of the world-state is
  exactly the set of open loops. Option A builds that face directly.
- **A mature loop tracker *is* a life-graph.** Once loops accumulate and are linked to
  entities/events/each other, "the graph" is what you have; "what's unfinished" is its most
  valuable projection.
- **The intervention engine is not Option B's alone — it's the output discipline both need.**
  The correlation engine already prototypes it (grounded hypothesis, explicit uncertainty,
  agency intact). Option A needs the *same* discipline to decide which drifting loop earns an
  interruption.

So the owner "wants A but leans B" because **A is the tractable substrate and B is the soul.**
You do not choose between them: A is the on-ramp; B is what A becomes once loops gain
relational structure and the surfacing discipline is trusted.

---

## Decision criteria

Choose the aperture that best satisfies, in order:

1. **Groundedness** — can every unit carry honest provenance and confidence? (favours A)
2. **Consumer for existing reflection** — does it give dream/insights/correlation something
   load-bearing to feed? (both; A more concretely)
3. **Lowest overengineering risk** — doctrine's explicit warning about B. (favours A)
4. **Fidelity to the long vision** — "connects things across your life." (favours B, but A
   reaches it by accretion)
5. **Demonstrable weekly value** — surfaces something the user would have missed / changes
   what they did. (A is easier to evidence early)

---

## Recommendation (ratified)

**Build Option A first, with Option B's intervention discipline designed in from day one.**

Concretely: make the *open loop* the first-class executive unit, but route every surfacing
decision through the correlation engine's grounded, uncertainty-preserving discipline — so the
system is a life-graph-with-intervention *in miniature* from the start, and grows into the full
B by accretion rather than by a second rewrite. This honours "want A, lean B": you ship A,
but nothing about it forecloses B, and B is the natural limit of iterating A.

The one hard constraint from the doctrine: whatever is built must be a **projection of the
world-state**, not a parallel structure beside it. A flat loop table that ignores the memory
graph would violate this and strand the path to B.

---

## What resolved this (delivered)

Delivered across two phases, per `specs/phases/109-open-loop-substrate/` and
`specs/phases/110-open-loop-drift-surfacing/`: schema and lifecycle
(`suspected → active → drifting → closed | dropped`), implicit extraction across all four
inflows (conversation, email, calendar, ingestion), drift detection (scheduled sweep + immediate
contradiction path), and surfacing policy (entity-overlap inline mentions with no gating, plus
a push path reusing the correlation engine's push-bar mechanics). The intervention discipline
was treated as a first-class requirement throughout, not a later add-on.

---

## Open Questions — resolved

- [x] **Ratify A-first, or override toward B-first?** Ratified A-first; shipped as
  `core/ze-worldstate`.
- [x] **Loop granularity** — flat, one loop per implicitly-detected item (promise, decision,
  drifting project); no sub-loop hierarchy was built. Goals remain a separate, un-unified
  concept (see `specs/phases/110-open-loop-drift-surfacing/spec.md` FR-014) — this is now a
  tracked follow-up, not an open design question here (see `contribution-seam.md`'s open
  questions and the loop/goal reconciliation gap noted in project memory).
- [x] **Extraction trust** — loops open in `suspected` state (`LoopState.SUSPECTED` in
  `ze_worldstate/types.py`), i.e. as low-confidence claims requiring corroboration before
  `active`, consistent with the doctrine's inference posture for perception-opened loops.
- [x] **Where it lives** — a new core package, `core/ze-worldstate` (not a promotion inside
  `ze-automation`), depending on `ze-agents`, `ze-proactive`, `ze-memory`, `ze-data`,
  `ze-components`, `ze-correlation`. Wired into `ze-api` directly, same pattern as
  `ze-automation`.
- [x] **Relationship to `memory_task_state` and goals** — neither reused nor superseded;
  open loops are a parallel primitive, deliberately not unified with goals (FR-014). This
  is flagged as unfinished business in the cognitive-architecture follow-up, not resolved here.
