# Contribution Seam — How the Seven Functions Write to the Spine

> **Status:** Partially ratified. The `Contribution` **type** (claim_kind/provenance/confidence
> + target_face/source_function/evidence) and its two retrofitted producers (`OpenLoop`,
> `Signal`) are ready to build now — see "Resolved" and "Phased rollout" below. The
> **arbitration mechanism** (a real conflict-resolution step, as opposed to a validated write
> path) remains design-only until reflection becomes a third client.
> **Scope:** `ze-plugin` (the seam itself), `ze-memory` / world-state (the target),
> `ze-core` governance (arbitration); every function-owning package downstream.
> **Constrained by:** `specs/arch/ze-doctrine.md` §The contribution model;
> `specs/arch/claim-topology.md` for the shared claim vocabulary the `Contribution` type builds on.
> **Relationship to the aperture:** the executive layer (`core/ze-worldstate`, ratified in
> `specs/arch/aperture-decision.md`) already exists and is one of the seam's two concrete
> producers.

---

## Context

The doctrine established that the seven cognitive functions each contribute to the world-state
in a licensed way, and named the direction: *"every function contributes through the same
uniform proposal seam, rather than through ad-hoc writes to memory tables."*

Today exactly **one** such seam exists — `SignalSource` (Phase 60), through which perception
proposes signals. Everything else writes directly: memory writes facts/episodes to its tables,
the dream pipeline writes synthesized artifacts, goals write to goal tables, correlation
returns hypotheses inline. There is no shared notion of "a function is proposing a change to
the spine, tagged with claim-kind + provenance + confidence, subject to arbitration."

This brief sets the grounds for generalising `SignalSource` into that shared seam. It is
explicitly **design-only**: the seam should not be built speculatively. It earns its existence
when the executive layer (aperture) gives it a second real client, so the abstraction is
extracted from two concrete cases — never invented ahead of one.

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
| Perception | facts, candidate loops | `SignalSource` (Protocol, registration hook only) producing `Signal` (no `claim_kind`, no real `confidence` — just `magnitude`) | **Resolved design, not yet wired** — `Signal` becomes a `Contribution` subtype (see below); `SignalSource` stays as-is, it was already the right registration mechanism |
| Memory | nothing new (custodian) | direct table writes | Memory is the *target*, not a contributor — mostly exempt |
| Executive | priorities, open-loop state | does not exist yet | **Built on the seam from day one** (aperture) |
| Social cognition | identity/relationship claims | contacts writes directly | Migrate after executive |
| Reflection | inferences, suspicions | dream/correlation write/return directly | High value — enforces "no facts from reflection" |
| Action | records of what it did | agents write results directly | Low priority — side effects, already grounded |
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
- **Wrap or replace direct writes.** Does the seam *replace* `store.propose_facts()` etc., or
  wrap them? Incremental migration argues for wrapping first, hard-cut later.
- **Arbitration mechanism.** Is arbitration a real conflict-resolution step (two contributions
  disagree → precedence decides) or initially just a validated write path? Start with the
  latter; add genuine conflict resolution when two functions actually collide.
- **Relationship to existing seams.** `memory_policies()`, `signal_sources()`, and the dream
  staging buffer are all proto-contributions. The seam should *subsume* them, not sit beside
  them — otherwise it is a third pattern, not a unifying one.
- **Where the type lives.** `ze-plugin` (shared extension seam) is the natural home for the
  `Contribution` contract; the arbiter lives in `ze-core` governance; the target is the
  world-state store.

---

## Phased rollout sketch (not a commitment)

The seam must be **extracted from two real clients, not invented before one.** Both trigger
conditions have now fired — the executive layer shipped (Phases 109–110) and its loop
extraction is an admitted "direct-write proto-contribution" (FR-017); perception's `Signal` has
also now been resolved to a `Contribution` subtype (above). Updated order:

1. ~~Executive layer ships (aperture, Option A).~~ **Done** — `core/ze-worldstate`, Phases
   109–110.
2. **Define the `Contribution` type and retrofit its two existing producers to it**
   (`specs/arch/claim-topology.md` covers the shared claim vocabulary this depends on):
   - `OpenLoop`'s extraction path keeps its current direct-write mechanics; it just now produces
     typed `Contribution`s instead of ad hoc loop-store calls.
   - `Signal` gains the shape resolved above.
   - **No consumer is rewired yet** — `ze-correlation` and `ze-worldstate` keep polling
     `signal_sources()` exactly as before; only the object shape changes.
3. **Migrate reflection onto it.** Highest safety payoff: mechanically forbids dream/correlation
   from writing facts. The dream staging buffer becomes a contribution queue. This is the first
   *third* client, and the point at which generalizing the arbitration mechanism (not just the
   type) actually earns its cost.
4. **Migrate social cognition** (relationship claims) and **action** (result records) as
   convenience allows. Low urgency.
5. **Add genuine arbitration** only once two functions demonstrably collide on the same
   world-state face.

Memory and governance are never "migrated" — they are the target and the arbiter.

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
- **Risk — big-bang migration.** Avoided by wrapping before replacing and migrating one function
  at a time.

---

## Open Questions

- [x] **Trigger to build.** Confirmed fired: executive layer (`ze-worldstate`) exists, and
  perception's `Signal` has a resolved `Contribution` design. The *type* is now due; the
  *arbitration mechanism* is still gated on reflection becoming a third client (step 3 above).
- [ ] **Sync vs staged per function** — resolve which functions arbitrate inline vs via a queue.
  Perception/executive likely sync (both already write inline in their current call paths);
  reflection likely staged (the dream staging buffer already is one).
- [x] **Does `Contribution` replace `Signal`, or is `Signal` a `Contribution` subtype?**
  Resolved above: subtype. `SignalSource` (the registration Protocol) is unchanged.
- [ ] **Confidence source** — resolved in *shape* by `specs/arch/claim-topology.md` (one
  `Confidence` value type, shared decay function); still open in *calibration* — LLM
  self-rating vs. corroboration count vs. feedback remains unresolved system-wide, per the
  doctrine's own open question.
