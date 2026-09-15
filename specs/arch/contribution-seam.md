# Contribution Seam — How the Seven Functions Write to the Spine

> **Status:** Mostly ratified and shipped. The `Contribution` **type**
> (claim_kind/provenance/confidence + target_face/source_function/evidence) lives in
> `core/contracts/ze-plugin/ze_plugin/contribution.py`; `OpenLoop`, `Signal`, and reflection (dream
> pipeline + correlation engine) all route through its validated write path as of Phase 124 —
> see "Resolved" and "Phased rollout" below. Phase 126 added collision *detection* (logging
> only) on top of this write path. Contacts (125) and social co-occurrence (130) also write
> through the seam. The remaining hole is **perception facts**: conversation
> `write_memory` and ingestion `MemorySink` still call `propose_facts()` ungated.
> The **arbitration mechanism** (a real conflict-resolution step, as opposed to a
> per-contribution claim-kind license check) remains design-only — Phase 126 exists to
> gather the evidence that would justify building it (step 8 below), and Phase 127 shipped
> one narrow, user-directed instance of arbitration (priority override) without
> generalizing the mechanism.
> **Scope:** `ze-plugin` (the seam itself), `ze-memory` / world-state (the target),
> `ze-core` governance (arbitration); every function-owning package downstream.
> **Constrained by:** `specs/arch/ze-doctrine.md` §The contribution model;
> `specs/arch/claim-topology.md` for the shared claim vocabulary the `Contribution` type builds on;
> `specs/arch/pre-v1-hard-cuts.md` (no wrap-then-replace until v1).
> **Relationship to the aperture:** the executive layer (`core/cognition/ze-worldstate`, ratified in
> `specs/arch/aperture-decision.md`) already exists and is one of the seam's two concrete
> producers.

---

## Context

The doctrine established that the seven cognitive functions each contribute to the world-state
in a licensed way, and named the direction: *"every function contributes through the same
uniform proposal seam, rather than through ad-hoc writes to memory tables."*

This brief originally described a seam that did not yet exist. The snapshot below is
historical. **Current state (2026-09-15)** follows.

Today exactly **one** such seam exists — `SignalSource` (Phase 60), through which perception
proposes signals. Everything else writes directly: memory writes facts/episodes to its tables,
the dream pipeline writes synthesized artifacts, goals write to goal tables, correlation
returns hypotheses inline. There is no shared notion of "a function is proposing a change to
the spine, tagged with claim-kind + provenance + confidence, subject to arbitration."

This brief sets the grounds for generalising `SignalSource` into that shared seam. It is
explicitly **design-only**: the seam should not be built speculatively. It earns its existence
when the executive layer (aperture) gives it a second real client, so the abstraction is
extracted from two concrete cases — never invented ahead of one.

### Current state (2026-09-15)

The type and the validated write path shipped. What did **not** ship is a closed
front door. These producers already call `validate_and_submit` /
`submit_and_detect_collisions`: `Signal` ingest, open-loop extraction (including
ingestion's loop hook), dream artifacts, correlation hypotheses, contact identity
writes, and social co-occurrence hypotheses.

These still write around it:

- Conversation `write_memory` → `MemoryStore.propose_facts()`
- Ingestion `MemorySink` → the same `propose_facts()`
- `memory_facts` still speaks a private provenance dialect (`"raw"` /
  `"synthesized"` on `Fact.provenance: str`); the INSERT path derives `claim_kind`
  from that string and does not persist a doctrine `Provenance`

That is the remaining house-cleaning: perception facts onto the seam, then a
hard-cut of the fact row onto the shared vocabulary. Pre-v1 hard cuts
(`specs/arch/pre-v1-hard-cuts.md`) forbid wrapping `propose_facts()` and leaving
it public.

---

## The concept: a Contribution

A **Contribution** is a function's typed proposal to change the world-state. Every contribution
carries, at minimum, the metadata the doctrine already mandates on every claim:

| Field | Meaning | Doctrine tie-in |
|---|---|---|
| `claim_kind` | identity / fact / inference / suspicion / priority | §epistemic ontology — the function may only emit kinds it is licensed for |
| `provenance` | `graph_recall` / `live_search` / `prompt_supplied` / `synthesized` / … | honest at the source, never from narration |
| `confidence` | how sure + decay rate | governs surfacing posture |
| `target_face` | self / user / world / active-concerns | which face of the spine it writes |
| `source_function` | perception / memory / … | enforces the licensing table |
| `evidence` | IDs of claims it rests on | inferences/suspicions must cite; enables cascade retraction |

Governance **arbitrates** contributions in the doctrine's precedence order (governance >
user-stated > fact > inference > suspicion) before any of them mutate the world-state. A
contribution is a *request*, not a write.

The critical rule the seam mechanically enforces, that convention cannot: **a function may only
submit contributions of the claim-kinds it is licensed for** — most importantly, *reflection
may never submit a fact.* Making this a property of the type system, not a guideline, is half
the reason the seam is worth building.

---

## Mapping the seven functions

Reuses the doctrine's licensing table; here framed as "what each function's contributions look
like" and how far each is from the seam today.

| Function | Contributes | Today | Distance to seam |
|---|---|---|---|
| Perception | facts, candidate loops | **Signals** on the seam (`ingest_signal`). **Loops** on the seam (`propose_loop_candidates`, including the ingestion hook). **Facts** from conversation and ingestion still call `propose_facts()` ungated | Next work: steps 5–6 below. `SignalSource` stays the registration Protocol |
| Memory | nothing new (custodian) | still exposes `propose_facts()` as a public write | Target, not a contributor — but the public back door must close in step 6. Memory does not originate claims |
| Executive | priorities, open-loop state | OpenLoop writes on the seam (Phases 109–110, 124); `PriorityView` ranks (123, 127, 132) | Write path done. Ranking consumer is Phase 132, not this brief |
| Social cognition | identity/relationship claims | Contacts on the seam (125); co-occurrence hypotheses on the seam (130) | Done for current producers |
| Reflection | inferences, suspicions | **On the seam** (Phase 124) — `dream_pass.py` and `ze_correlation/engine.py` route their writes through `Contribution`, which rejects `claim_kind=FACT` before the store is reached | Done — "no facts from reflection" is now type-enforced, not conventional |
| Action | records of what it did | agents write results directly | Low priority — side effects, already grounded (step 7) |
| Governance | confidence/consent/provenance metadata | capability gate, review flows | Governance *is* the arbiter, not a contributor |

Two functions are special: **memory is the target** (contributions land in it), and
**governance is the arbiter** (it evaluates contributions). The seam is really about the other
five *producing* into memory via governance.

---

## Resolved: `Signal` is a `Contribution` subtype, not a parallel type

This was the open question "does `Contribution` replace `Signal`, or is `Signal` a
`Contribution` subtype?" It matters more than it looks, because today `Signal` is not actually
a contribution to the shared world-state at all — it is a **private pull channel** between
perception plugins and exactly two privileged consumers (`ze-correlation`, `ze-worldstate`),
who poll `signal_sources()` and then write their *own* derived claims (hypotheses, loops) to
the spine. Perception itself never lands a fact on the shared world-state through this path.
That is in tension with the doctrine's "nothing holds a competing private truth" — `Signal` is
quietly a competing private truth today, just a short-lived one, invisible because nobody reads
it as history.

**Resolution:** `Signal` becomes a `Contribution` subtype:

- `claim_kind` is always `FACT` — perception's sole licensed claim-kind (doctrine's
  contribution model table).
- `provenance` and a real `confidence` come from the shared `ze_agents.claims` vocabulary
  (`specs/arch/claim-topology.md`), not a bespoke field.
- `magnitude` (relevance) stays a distinct field alongside `confidence` — they are different
  concepts (how much this matters vs. how sure we are it's true) and claim-topology's mapping
  pass confirmed conflating them would be a regression, not a simplification.
- The `SignalSource` Protocol is **not replaced** — it was already the correct shape for "how a
  plugin registers as a perception source." It simply now returns `Contribution`-typed objects
  instead of the current bespoke `Signal`.

**Explicitly deferred, not part of this resolution:** rewiring `ze-correlation` and
`ze-worldstate` to consume contributions via a shared seam/queue instead of polling
`signal_sources()` directly. That is a real behavior change to two live consumers and belongs
in a follow-up phase once the loop-extraction migration (below) has proven the seam holds up
end-to-end — not something to change at the same time as the type definition. Until that
follow-up, `Signal` is a `Contribution` in shape only; the delivery mechanism is unchanged.

---

## Design questions to resolve before speccing

- **Runtime type vs store.** Is a Contribution an in-process object arbitrated synchronously in
  the graph, a persisted queue (like the dream staging buffer), or both depending on function?
  (Perception/executive likely sync; reflection likely staged — it already is.)
- ~~**Wrap or replace direct writes.**~~ **Replace.** Pre-v1 (`specs/arch/pre-v1-hard-cuts.md`)
  forbids wrap-then-replace across phases. `propose_facts()` MUST stop being a public
  ungated write: callers submit a `Contribution`; the store write is only the `write=`
  callback. A phase may wrap internally while call sites move; the old public entry
  point is gone when that phase is Done.
- **Arbitration mechanism.** Is arbitration a real conflict-resolution step (two contributions
  disagree → precedence decides) or initially just a validated write path? Start with the
  latter; add genuine conflict resolution when two functions actually collide. Undeployed
  status does not skip the evidence gate.
- **Relationship to existing seams.** `memory_policies()`, `signal_sources()`, and the dream
  staging buffer are all proto-contributions. The seam should *subsume* them, not sit beside
  them — otherwise it is a third pattern, not a unifying one.
- **Where the type lives.** `ze-plugin` (shared extension seam) is the natural home for the
  `Contribution` contract; the arbiter lives in `ze-core` governance; the target is the
  world-state store.

---

## Phased rollout

The seam must be **extracted from two real clients, not invented before one.** Both trigger
conditions fired (executive layer shipped, `Signal` resolved to a `Contribution` subtype), and
the rollout has since moved past step 3. Remaining steps are a commitment, not a sketch.
**Do not start steps 5–6 while Phase 132 (priority turn surfacing) is still open.** Product
surface first; substrate next. Number the two feature specs at `/speckit-specify` time.

1. ~~Executive layer ships (aperture, Option A).~~ **Done** — `core/cognition/ze-worldstate`, Phases
   109–110.
2. ~~Define the `Contribution` type and retrofit its two existing producers to it.~~ **Done** —
   Phase 124. `OpenLoop`'s extraction path and `Signal` both produce typed `Contribution`s;
   `ze-correlation`/`ze-worldstate` were not rewired to consume contributions and still poll
   `signal_sources()` exactly as before, per that phase's own scope guard (FR-008).
3. ~~Migrate reflection onto it.~~ **Done** — Phase 124 shipped this in the same feature as
   step 2, rather than as a separate follow-up (see that phase's User Story 2). The dream
   pipeline's `dream_pass.py` and `ze-correlation`'s `engine.py` both route their writes
   through `Contribution`; a `claim_kind=FACT` submission from either is rejected before any
   store is reached. The dream staging buffer itself was **not** replaced with a persisted
   contribution queue — "migrate onto the seam" ended up meaning "the existing write call
   passes through the validated wrapper," per Phase 124's own Assumptions section, not a
   staging-architecture rewrite.
4. ~~Migrate social cognition (relationship claims).~~ **Done** for current producers —
   contacts (125), social-cognition foundation (128), co-occurrence hypotheses (130).
5. **Perception facts on the seam** (next feature spec after Phase 132). Two call
   sites, one shape already used by `ingest_signal`:
   - `ze_core/orchestration/nodes/memory.py` (`write_memory` → `propose_facts`)
   - `ze_ingestion/sink.py` (`MemorySink` → `propose_facts`)
   Each fact is a `Contribution` with `source_function=perception`, `claim_kind=FACT`,
   shared `Confidence`, and honest provenance (resolved below). Ingestion's
   `ingestion_id` becomes evidence / `source_refs` (Phase 69 promised this and never
   landed). Plugin extractors (finance, etc.) keep writing their own tables; the
   fact strings they return take this path. Open-loop extraction from ingestion
   already on the seam stays as-is. When this phase is Done, those two callers no
   longer call ungated `propose_facts()`.
6. **Hard-cut `memory_facts` onto the shared vocabulary** (feature spec after step 5).
   `Fact` and the `memory_facts` row use `ClaimKind` / `Provenance` / `Confidence`
   for real. Drop the `"raw"` / `"synthesized"` string dialect. Persist provenance
   on insert. `propose_facts()` is no longer a public ungated API — either private
   to the seam's `write=` callback or deleted. Schema churn is allowed
   (`pre-v1-hard-cuts.md`). This is the leftover from `claim-topology.md`, not a
   new theory of memory.
7. **Action** (result records) as convenience allows. Low urgency. Same seam, same
   hard-cut rule, not bundled into steps 5–6.
8. **Add genuine arbitration** only once two functions demonstrably collide on the same
   world-state face. Phase 126 (contribution collision *detection*) exists to make that trigger
   condition observable — it logs collisions but still doesn't arbitrate them. No cross-function
   arbitration mechanism has been built yet; Phase 127 (priority override) shipped one narrow,
   user-directed arbitration case (decaying/pinned overrides merged into `PriorityView.rank()`)
   without generalizing this step. Pre-v1 hard cuts do **not** license skipping this gate.

Memory and governance are never "migrated" as producers — they are the target and the arbiter.
Step 6 only removes memory's accidental role as an ungated writer.

### Out of this rollout

- Loop/goal store merge (Phase 110 FR-014). Ranking is Phase 132.
- Rewiring `signal_sources()` polling into a contribution queue (explicitly deferred
  in Phase 124 FR-008).
- Confidence *source* (LLM self-rating vs corroboration vs feedback) — still the
  doctrine's open question; shape is already shared.
- Ingest archive UX (`GET /api/v0/ingest`), graphing extracted entities as a
  general promotion, sensors. Hygiene, not doctrine.
- A "delete all historical package-split shims" mega-spec.

---

## Consequences and risks

- **Positive:** enforces the doctrine's licensing rules in code, not prose; makes provenance and
  confidence universal rather than per-subsystem; unifies three existing proto-seams; gives the
  arbitration order a single chokepoint.
- **Risk — premature abstraction.** This is the doctrine's own anti-pattern ("a sentence that
  hardened into metaphysics"). Mitigated by the extract-from-two-clients rule: nothing here is
  built until the executive layer forces it.
- **Risk — performance.** A synchronous arbitration step sits in the hot path for
  perception/executive contributions. The correlation engine's inline latency discipline (hard
  timeout, silent drop) is the precedent to follow.
- **Risk — big-bang migration.** Avoided by migrating one function at a time (steps 5 then 6),
  not by leaving the old API alive. Pre-v1 hard cuts make the cut per phase, not a wrap that
  lasts until v1.

---

## Open Questions

- [x] **Trigger to build.** Confirmed fired: executive layer (`ze-worldstate`) exists, and
  perception's `Signal` has a resolved `Contribution` design. The *type* shipped in Phase 124
  along with reflection as a third client (step 3 above, done); the *arbitration mechanism* is
  now gated on Phase 126's collision evidence accumulating (step 8), not on a third client
  existing.
- [x] **Sync vs staged per function** — resolved by how Phase 124 actually wired reflection:
  the correlation engine's write is synchronous/inline (`engine.py` calls through the
  `Contribution` wrapper at hypothesis-save time); the dream pipeline's write stays staged (the
  existing artifact-staging buffer is unchanged — the seam wraps the write call, it did not
  become a new persisted contribution queue). No function was moved off its natural sync/staged
  posture to adopt the seam; the seam validates whichever posture a producer already has.
- [x] **Does `Contribution` replace `Signal`, or is `Signal` a `Contribution` subtype?**
  Resolved above: subtype. `SignalSource` (the registration Protocol) is unchanged.
- [x] **Wrap or replace `propose_facts()`?** Replace. See Design questions and
  `specs/arch/pre-v1-hard-cuts.md`.
- [x] **Epistemic provenance for extracted facts.** LLM-extracted facts (conversation
  turn or ingested document) stamp `Provenance.SYNTHESIZED`. Explicit
  `memory_proposals` from the user/agent stamp `Provenance.PROMPT_SUPPLIED`. The
  inflow channel (`conversation`, `ingestion`, plugin key, …) is the plugin-owned
  string from `specs/arch/plugin-domain-vocabulary.md`, not a `Provenance` member.
  Ingestion's archive id travels as evidence / `source_refs`, not as provenance.
- [ ] **Confidence source** — resolved in *shape* by `specs/arch/claim-topology.md` (one
  `Confidence` value type, shared decay function); still open in *calibration* — LLM
  self-rating vs. corroboration count vs. feedback remains unresolved system-wide, per the
  doctrine's own open question.
