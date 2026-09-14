# Social Cognition — People, Projects, and Relationships as Evolving State

> **Status:** Proposed — design questions resolved. Rollout steps 1–2 shipped as
> Phase 128; step 3 is specced as
> [`specs/phases/130-social-cognition-co-occurrence/spec.md`](../phases/130-social-cognition-co-occurrence/spec.md)
> (not yet implemented). Step 4 remains deferred.
> **Scope:** `core/cognition/ze-memory` (the graph), `plugins/ze-personal` (contacts, the existing
> partial implementation), `core/cognition/ze-correlation` (co-occurrence inference), `core/arbitration/ze-priority`
> (surfacing), `core/contracts/ze-proactive` (the shared staleness helper reused below),
> `core/contracts/ze-communication`/`ze-messenger`/`ze-calendar` (the inflows).
> **Constrained by:** `specs/arch/ze-doctrine.md` §The contribution model (social cognition is
> licensed for `ClaimKind.IDENTITY` only — "identity/relationship claims, boundaries"; it may
> not emit facts about the world, and its inferences must arrive via reflection first, same as
> every other function); `specs/arch/claim-topology.md` (the `Confidence`/decay vocabulary this
> brief reuses rather than inventing new decay math); `specs/arch/contribution-seam.md` (the
> write path `Person` already uses and `PersonRelationship`/`project` will use — no seam work
> required, see "What already exists" below).
> **Research basis:** absorbed into this document (see "Research basis" at the end) — four
> parallel research passes on personal-CRM data models, PKM/knowledge-graph systems, AI-agent
> memory architectures, and relationship-decay/co-occurrence inference, condensed to the
> claims this brief actually leans on. The original raw report has been retired in favor of
> this matured document.
> **Relationship to the doctrine's gap list:** `docs/cognitive-architecture.md`'s sequencing
> section names this "the same gap seen twice" — social cognition's third-party relationship
> modeling and memory's missing "state of project X" / "state of relationship with Y" are one
> gap, not two.

---

## Context

The owner wants Ze to correlate **projects** with the **people who work on them**, model
**relationships in general**, and feed both from the communication channels Ze already
ingests (email, calendar, messaging) — not as a contacts directory, but as state that changes
over time. Per `docs/cognitive-architecture.md`, this is the one remaining function-level gap
with no design brief: social cognition is rated 🟡 partial (persona/tone toward the user is
well-modeled; third-party relationship modeling is thin, "a directory, not a relationship
model").

This brief exists to answer, before anything is specced: what's the primitive (a new store, or
an extension of what exists), what's the minimal state worth tracking, how does project-person
correlation get inferred from communication data without duplicating `ze-correlation`, and
where's the line between a useful nudge and a surveillance-feeling one. A round of prior-art
research (personal-CRM tools, PKM/knowledge-graph systems, AI-agent memory architectures,
relationship-decay and co-occurrence-inference literature) did the legwork; its claims are
condensed into "Research basis" at the end of this document, and every design decision below
cites the specific finding it rests on.

---

## What already exists (read this before designing anything new)

This is not a greenfield gap — there is a partial, unwired implementation already in the
codebase, and it repeats a mistake the doctrine has already named once.

- **`SourceFunction.SOCIAL_COGNITION` already has a live producer — for `Person`, not
  relationships.** `plugins/ze-personal/ze_personal/contacts/contribution.py`'s
  `person_source_to_contribution()` converts a `PersonSource` into a `Contribution`
  (`claim_kind=IDENTITY`, `confidence` using `DecayProfile.EVIDENCE_WEIGHTED` off the existing
  `SOURCE_WEIGHTS` table — `manual`/`conversation`=1.0, `email`=0.7, `calendar`=0.6,
  `research`=0.2), and both `contacts/consolidator.py` and `graph/memory_hooks.py` route
  through it via `submit_and_detect_collisions()` — the full Phase 124/126 write path,
  collision detection included. `Person` is also correctly synced into the memory graph
  (`PersonStore._write_entity()` upserts an `Entity(entity_type="person", ...)`). **People are
  fully on the seam already.** This brief's real gap is relationships and projects, not people.
- **`plugins/ze-personal/ze_personal/contacts/types.py`'s `PersonRelationship` type
  (`person_a_id`, `person_b_id`, a free-text `relationship_description`, a plain
  `confidence: float`) is dead code in production.** `PersonStore.add_relationship()` /
  `get_relationships()` write to a `contact_relationships` table (added in migration
  `zc005_contacts_and_channels.py`, no seed data) — but grepping the whole repo for callers
  turns up only `plugins/ze-personal/tests/contacts/test_person_store.py`. No agent tool, job,
  or API route ever calls either method. It is real schema, never wired to a producer — the
  same "built following the right instinct, before the graph existed to reconcile it into"
  situation `aperture-decision.md` describes for loops, except here nothing ever ran, so there
  is no live data and no migration to plan (see "Resolved design questions" below). Had it
  been wired, it would be **a second, parallel graph duplicating `core/cognition/ze-memory`'s
  `memory_relationships`** — the exact anti-pattern `aperture-decision.md` warned against
  ("a flat loop table that ignores the memory graph would violate this and strand the path to
  B"). This brief retires it outright rather than migrating it.
- **`StaleFollowUpNudge` (same file) is live**, unlike `PersonRelationship`:
  `PersonStore.list_stale_for_follow_up(stale_days, limit)` is called from
  `ze_personal/jobs/briefing.py` today — but it uses a fixed `stale_days` config threshold,
  predates `core/arbitration/ze-priority`'s `PriorityView` (Phase 123), and is not budget-gated through
  it. It is its own independent, unranked nudge channel, dedup'd only by a 20-hour `push_log`
  cooldown on the whole briefing, not by `PriorityView`'s shared attention budget.
- **`core/cognition/ze-memory`'s `Relationship` dataclass** (`ze_memory/graph/types.py`) has the right
  shape for a typed, provenanced, confidence-scored edge (`predicate`, `confidence`,
  `provenance_id`, `creation_method: explicit|extracted|synthesized`). Its predicate
  vocabulary (`core/cognition/ze-memory/ze_memory/graph/predicates.py`) is deliberately closed —
  `MENTIONS`, `PARTICIPATES_IN`, `DESCRIBES`, `SOURCED_FROM`, `USES_PROCEDURE`,
  `BELONGS_TO_GOAL`, `PROMOTES_TO` — and the file's own header states the extension policy:
  "only extend this list when a concrete retrieval or audit use case demands it." Note
  `PARTICIPATES_IN` is documented as **event → entity** ("event participates in / targets an
  entity"), not entity ↔ entity — it does **not** already fit a person↔project edge; two new
  predicates are a sanctioned addition under the file's own policy (see "Resolved design
  questions").
  Its `confidence` field is a plain `float`, not yet the shared `ze_agents.claims.Confidence`
  type — this predates Phase 111's claim-topology retrofit and was not swept up in it.
- **`ze_agents.claims` ships `DecayProfile.TIME_LINEAR`** (`_TIME_LINEAR_RATE = 0.03` per
  `_TIME_LINEAR_PERIOD_DAYS = 30.0`, a fixed, non-per-caller-tunable rate) and it is already
  in wide production use for exactly this shape of "confidence should fall as time passes"
  problem: `core/cognition/ze-correlation`'s `HypothesisDecayJob` (`DEFAULT_DECAY_WINDOW_DAYS = 30`),
  the dream promoter (`elapsed_days=30.0`), and `core/arbitration/ze-priority`'s urgency scoring
  (`scoring.py`, `elapsed_days=stuck.idle_days`) all reuse the same fixed rate rather than each
  tuning their own. `core/contracts/ze-proactive/ze_proactive/staleness.py`'s `is_stale(timestamp,
  window_days)` is the shared helper behind several of these sweeps.
- **No `project` (or any project-shaped) entity type exists anywhere** — not in
  `core/cognition/ze-memory`'s `entity_type` set (`person | org | topic | ticker | place | product`),
  not in `ze-automation`'s goals/workflows (those are the user's own declared work items, not
  a container correlating other people to a shared context).

**The upshot:** people are already fully on the seam and in the graph. The actual gap is
narrower than it first looked: a `project` entity type, two new predicates, and retiring one
piece of dead schema that was built with the right instinct but never wired.

---

## The concept

Two additions to the existing memory graph, no new store:

1. **`project` becomes a new `entity_type`** in `core/cognition/ze-memory`, alongside
   person/org/topic/ticker/place/product. A project is whatever the user is working on that
   involves other people — it is discovered the same way contacts are (extraction from
   conversation/email/calendar), not manually declared as a prerequisite.
2. **Person↔person and person↔project edges live in `memory_relationships`**, via two new
   entries in `core/cognition/ze-memory/ze_memory/graph/predicates.py`'s controlled vocabulary:
   `WORKS_ON` (person → project) and `COLLABORATES_WITH` (person ↔ person) — `PARTICIPATES_IN`
   is already spoken for (event → entity) and isn't reused. `contact_relationships` is retired
   outright, not migrated (see "Resolved design questions" — it never had a live producer).

Per research: no AI-agent memory architecture examined (Mem0, Letta/MemGPT, Zep/Graphiti,
LangGraph) treats "social memory" as a distinct structure, and the one production system with
a project/context-clustering primitive (Zep/Graphiti's Community Subgraph) implements it as
generic entity clustering, not a people-specific subsystem. This is exactly what extending
`core/cognition/ze-memory` this way produces.

### Relationship state — minimal, not a scoring engine

Per research finding R3/R7 (see appendix), add exactly two fields to the edge, not a
strength/warmth score:

- `last_contact` — a timestamp, **computed from the communication graph** (last message,
  meeting, or thread touching both endpoints), never manually set. This is what every personal-
  CRM tool researched treats as non-negotiable: manually-set last-contact dates go stale the
  moment logging lapses (R3, R5's Monica citation).
- `confidence`, retrofitted from the current plain `float` to `ze_agents.claims.Confidence`
  with `DecayProfile.TIME_LINEAR` — reusing, not inventing, decay math. This *is* the
  relationship-staleness signal; a separate "cadence" field (a target interval the user sets)
  is deliberately **out of scope for v1** — see Phased rollout.

No continuous multi-factor "relationship strength" score (recency × intensity × reciprocity,
per R6's Gilbert & Karahalios feature set) is built in v1. It's a defensible, literature-backed
model, but R7 found no production system has validated it against real outcomes — premature
for a v1.

---

## Decision: extend the graph, don't build a parallel store

This mirrors `aperture-decision.md`'s reconciliation logic almost exactly: **a mature
relationship tracker *is* a knowledge graph; "who's connected to what" is its most valuable
projection.** The alternative (a dedicated `ze-social` package with its own store) was
considered and rejected for the same reason the doctrine rejected it for loops:

| | Extend `core/cognition/ze-memory` (recommended) | New `ze-social` store |
|---|---|---|
| Precedent | R1/R2: every AI-memory architecture researched | None found — no system researched has a standalone social-memory store |
| Reuses existing work | `Relationship` dataclass, predicate vocabulary, `GraphStore.expand()`, `/brain/graph` UI (Phase 94), `Confidence`/decay (Phase 111) | Nothing — duplicates all of the above |
| Fixes the existing violation | Yes — retires `contact_relationships` | No — adds a third parallel structure alongside `memory_relationships` *and* `contact_relationships` |
| Query surface | One graph, already has entity-anchored retrieval (Phase 106) | A second graph the retrieval/correlation/priority layers would all need to learn to query |

---

## How project-person correlation gets inferred (not a new subsystem)

Per research findings R8/R9, this is the part of the brief with the clearest evidence and the
sharpest guardrail: **every production organizational-network-analysis tool researched uses a
bounded recency window, never an all-time cumulative count**, specifically because (a) old
co-presence goes stale and (b) CC/broadcast recipients inflate apparent involvement independent
of actual participation (R8's Christidis & Gomez Losada citation).

This maps directly onto machinery Ze already has, and should not get a new subsystem:

1. **Perception** (unchanged) continues emitting `FACT`-kind contributions for raw
   communication events — email received, calendar event attended, message thread joined.
   Already licensed, already happening.
2. **`ze-correlation`** forms the hypothesis "person P and person Q likely collaborate on
   project R," scored from recency-weighted, non-CC-weighted evidence — an `INFERENCE`-kind
   `Contribution`, exactly the same shape as any other correlation hypothesis, with evidence
   and confidence. **No new correlation subsystem is built**, and neither the window nor the
   weighting is invented from scratch (see "Resolved design questions" for both):
   - **Recency window: 30 days**, via `core/contracts/ze-proactive/ze_proactive/staleness.py`'s existing
     `is_stale(timestamp, window_days)` helper — the same window
     `HypothesisDecayJob.DEFAULT_DECAY_WINDOW_DAYS`, the dream promoter, and `TIME_LINEAR`'s
     own decay period already use. Evidence outside the window doesn't count.
   - **Evidence weighting reuses `ze_personal.contacts.types.SOURCE_WEIGHTS`** (already tuned:
     `manual`/`conversation`=1.0, `email`=0.7, `calendar`=0.6, `research`=0.2) rather than a
     new CC-discount formula — a same-thread reply is `conversation`-tier evidence, a
     CC-only/no-reply mention is `research`-tier. This directly implements the "recency +
     de-weighted broadcast noise" pattern found across every production organizational-network
     tool researched.
   This also gives project-person inference the same collision-detection visibility
   (Phase 126) as every other contribution.
3. **Promotion to `IDENTITY`** happens the same way dream/insight promotion already works:
   once a hypothesis is sufficiently corroborated (repeated pattern across enough
   recency-windowed evidence, or the user confirms it — mirroring `PersonStore.confirm()`'s
   existing pending→confirmed flow for contacts), it is written as a `memory_relationships`
   edge under `SourceFunction.SOCIAL_COGNITION`'s existing `ClaimKind.IDENTITY` license. Until
   then, it stays an inference — visible if asked about, not asserted as settled.

This keeps reflection from ever emitting a fact about who's on what project, which is exactly
the doctrine's load-bearing rule, applied to a new domain instead of relaxed for it.

### Termination — don't formally close a project

Per the Viva Insights finding below (a rolling window lets stale collaborators silently
drop out of the *view* without ever closing the *entity*): a `project` entity does not need an
explicit lifecycle state (`active`/`closed`, mirroring `OpenLoop`). Membership is computed
fresh from the recency window each time `PriorityView`-style surfacing or the graph view asks
"who's currently on this," the same way `PriorityView` itself computes fresh rather than
persisting a ranked list. This sidesteps the "when does a project end" question a
`goal`/`loop`-style state machine would force.

---

## Surfacing — reuse `PriorityView`, retire the unbudgeted nudge

`StaleFollowUpNudge`/`list_stale_for_follow_up` is real and shipping today, but it predates
`core/arbitration/ze-priority` and bypasses its shared attention budget entirely — it is exactly the
per-mechanism nudge channel Phase 123 was built to eliminate for loops/goals/hypotheses. Per
research finding R5, the creepy-vs-useful line real products draw is transparency of *why* a
nudge fired, not whether automatic inference happens at all — Ze already clears that bar
(contacts are already auto-extracted, with provenance).

Recommendation: fold relationship-staleness nudges into `PriorityView` as a fourth ranked
source (alongside loops, goals, hypotheses) rather than leaving them as the morning briefing's
own fixed-threshold side channel. This is plumbing, not new interruption policy — `PriorityView`
already degrades gracefully per source (FR-009 of Phase 123) and already exists to solve
exactly this "N independent nudge mechanisms, one budget" problem.

---

## Phased rollout sketch (not a commitment)

Per `contribution-seam.md`'s own precedent, extract from real usage rather than build
speculatively. `StaleFollowUpNudge` is real usage to extract from; `contact_relationships` is
not (it's dead schema, per "What already exists") — so phase 1 is a mix of "retire" (the dead
piece) and "build" (the new entity type and predicates), not a data migration.

1. **Add `project` as an `entity_type`; retire `contact_relationships` outright** (drop the
   table and the `PersonRelationship`/`add_relationship`/`get_relationships` code — no data to
   move, per "Resolved design questions"). Add `WORKS_ON` and `COLLABORATES_WITH` to
   `core/cognition/ze-memory/ze_memory/graph/predicates.py`. Retrofit `Relationship.confidence` from
   plain `float` to `ze_agents.claims.Confidence` with `DecayProfile.TIME_LINEAR`. No new
   inference yet — this alone makes people/projects/relationships queryable in one graph and
   visible in the existing `/brain/graph` view.
2. **Wire `list_stale_for_follow_up` into `PriorityView`** instead of the morning briefing's
   own fixed-threshold path — makes relationship-staleness a ranked, budget-gated source like
   loops/goals/hypotheses, closing the reconciliation gap noted above.
3. **Project-person co-occurrence inference via `ze-correlation`**, using the 30-day window and
   `SOURCE_WEIGHTS`-based evidence weighting resolved above, promoted to `IDENTITY` on
   corroboration per the promotion pattern above. This is the first genuinely new capability in
   the rollout; everything before it is reconciliation of what already exists.
4. **Explicitly deferred, not part of this brief:** a continuous multi-factor relationship-
   strength score; user-settable cadence as a field distinct from computed `last_contact`
   (worth revisiting only if fixed `TIME_LINEAR` decay proves too coarse in practice); per-
   thread (vs. recency-window) project membership refinement (no source found validates this
   is needed beyond what the recency window already buys — see "Resolved design questions").

---

## Consequences and risks

- **Positive:** retires a real piece of unwired dead schema (`contact_relationships`) as part
  of delivering the new capability, rather than as a separate cleanup nobody schedules. Reuses
  five already-built mechanisms (`Relationship`, `Confidence`/decay, `ze-correlation`,
  `PriorityView`, `SOURCE_WEIGHTS`) instead of adding a sixth. Gives "state of project X" and
  "state of relationship with Y" — `docs/cognitive-architecture.md`'s named gap — a real,
  provenance-linked answer.
- **Risk — the briefing's `stale_days`/`max_nudges` config keys change meaning.** Folding
  `list_stale_for_follow_up` into `PriorityView` (rollout step 2) removes the morning
  briefing's direct control over its own stale-contact threshold — it becomes one ranked
  input among several, governed by the shared attention budget instead of its own config.
  This is a deliberate behavior change (the point of Phase 123), but worth calling out
  explicitly in the eventual phase-2 spec rather than treating it as a transparent refactor.
- **Risk — inference creepiness, despite the transparency discipline.** Products succeed on
  the automatic-inference side of the personal-CRM market only when they show their work; a
  project-inference hypothesis that's wrong (e.g., inferred from a CC'd distribution list
  despite the recency discount) and gets surfaced before corroboration would read as
  presumptuous. The promotion-on-corroboration gate (never surface an unconfirmed `INFERENCE`
  as if it were settled) is the mitigation, same as it is for every other reflection output.
- **Risk — premature generality, deliberately accepted.** `COLLABORATES_WITH` as a single
  predicate for all person↔person relationships is coarse (colleague, family, friend all
  collapse into one edge type) — deliberately so for v1, per the resolved decision below.
  Revisit only with evidence it's needed.

---

## Resolved design questions

All four questions from the first draft are settled. None are blocked on further research —
each resolves from either a codebase fact gathered while drafting this brief, or an explicit
"reuse the existing convention over inventing a new one" call.

- [x] **Migration mechanics for `contact_relationships` → `memory_relationships`.** Resolved:
  there is no migration. Repo-wide grep for `add_relationship`/`get_relationships` callers
  turns up only `plugins/ze-personal/tests/contacts/test_person_store.py` — no agent tool,
  job, or API route has ever written a row. `contact_relationships` (migration
  `zc005_contacts_and_channels.py`) ships no seed data either. Phase 1 drops the table and
  the dead `PersonRelationship` type in the same change that adds `project` and the two new
  predicates — a retirement, not a data migration. (This does **not** apply to
  `StaleFollowUpNudge`/`list_stale_for_follow_up`, which is live and handled separately in
  rollout step 2, reading from `Person.last_mentioned`, not `contact_relationships`.)
- [x] **`COLLABORATES_WITH` vs. a small closed predicate set.** Resolved: ship one predicate
  (`COLLABORATES_WITH`) for v1, not a taxonomy. `Person.classification`
  (`"personal"|"professional"|"unknown"`, already a field on `Person`) already gives a cheap,
  existing way to filter/color relationships by domain without a second predicate — reuse
  that field rather than encoding the same distinction twice. Personal-CRM and PKM research
  converged on the same call: Notion's Relation property is the one mainstream system with a
  real typed-relation schema, and even it doesn't put finer semantics on the *edge* — every
  system researched keeps relationship-type nuance on the node or a sibling field, never a
  large predicate vocabulary on the edge itself. Revisit only if `COLLABORATES_WITH` proves
  too coarse in practice — no evidence today says it will.
- [x] **Where the co-occurrence inference threshold lives, and what the numbers are.**
  Resolved: a 30-day recency window via `core/contracts/ze-proactive/ze_proactive/staleness.py`'s
  existing `is_stale()` helper — the same window already used by
  `HypothesisDecayJob.DEFAULT_DECAY_WINDOW_DAYS`, the dream promoter's `elapsed_days=30.0`,
  and `TIME_LINEAR`'s own `_TIME_LINEAR_PERIOD_DAYS`. Evidence weighting reuses
  `ze_personal.contacts.types.SOURCE_WEIGHTS` verbatim (manual/conversation=1.0, email=0.7,
  calendar=0.6, research=0.2) rather than a new CC-discount formula. Neither number is
  research-validated in an absolute sense (no source found gives a validated window width for
  *this* problem specifically — the closest external precedent, Microsoft Viva Insights'
  4-week collaborator window, is for a very different enterprise/multi-user context), but both
  are Ze's own existing, already-shipped conventions for "how stale is too stale" and "how
  much does this kind of evidence count" — internal consistency beats inventing new,
  unvalidated numbers when no external source can settle it either.
- [x] **Does `TIME_LINEAR` decay actually fit relationship staleness, or does it need its own
  profile?** Resolved: reuse `TIME_LINEAR` as-is, no relationship-specific decay profile.
  Two reasons. First, no source anywhere — commercial relationship-management tool, PKM
  system, or academic tie-strength/decay literature — has a validated decay formula for
  interpersonal ties specifically; the Ebbinghaus-forgetting-curve framing popular in CRM-app
  marketing copy is an unvalidated analogy wherever it appears, so there is no external number
  to adopt instead of Ze's own. Second, and more load-bearing: `claim-topology.md`'s entire
  point (Phase 111) was collapsing per-subsystem decay logic into one shared function so
  confidence means the same thing everywhere — `HypothesisDecayJob`, the dream promoter, and
  `PriorityView`'s urgency scoring already all share the one `TIME_LINEAR` rate rather than
  each tuning their own. Giving relationships a bespoke rate would be exactly the
  per-subsystem proliferation Phase 111 exists to prevent, for a domain with no evidence that
  it actually needs a different rate.

---

## Research basis

Condensed from four parallel research passes (personal-CRM data models, PKM/knowledge-graph
systems, AI-agent memory architectures, relationship-decay + co-occurrence inference) run
2026-08-26, ~55 searches total. Only the findings this brief actually leans on are kept; each
is the claim + its confidence level, not a full citation trail. The original raw report
(`docs/research/social-cognition.md`) has been retired now that its substance lives here.

- **R1 — No AI-agent memory architecture treats "social memory" as a formally distinct
  category.** Mem0, Letta/MemGPT, Zep/Graphiti, Stanford's Generative Agents, and LangGraph
  all fold social/relational state into a generic entity/relationship graph (or, for
  Generative Agents, treat it as emergent from generic episodic memory) rather than a named
  parallel structure. HIGH confidence — corroborated across independent primary sources
  (arXiv papers, vendor docs) for all five systems.
- **R2 — Only two systems have any project/context-clustering primitive, both generic.**
  Zep/Graphiti's "Community Subgraph" clusters any entity type by connectivity, not people
  specifically (HIGH — official docs + arXiv). Letta's experimental `ai-memory-sdk` has
  named "Subjects" (`project_alpha`, `team_support`) as isolated-memory containers (MEDIUM —
  experimental package, not core product).
- **R3 — Typed-relation schemas beat bare backlinks but go stale without an update
  mechanism.** Notion's Relation+Rollup is the one mainstream PKM mechanism giving a
  relationship real queryable structure, but is manually maintained and repeatedly critiqued
  for going stale the moment logging lapses. Backlink-only tools (Obsidian/Roam/Logseq)
  auto-populate but carry no type or state at all. HIGH confidence on the mechanisms; MEDIUM
  on the general framing (clean single-source statement of a pattern visible across 5 tools).
- **R5 — Personal-CRM tools split cleanly into "automatic + transparent" (Clay, Dex) vs.
  "manual + private" (Monica), no hybrid found.** Dex's stated mitigation for the automatic
  side: "analyzes metadata... without accessing the content of personal communications."
  MEDIUM-HIGH confidence (multiple independent reviews per tool; Monica's own anti-tracking
  philosophy is the one first-party design statement found).
- **R6 — Tie-strength prediction: recency + intensity/frequency dominate.** Granovetter
  (1973, foundational) and Gilbert & Karahalios (CHI 2009, peer-reviewed, 2,184 ties measured)
  found Intimacy (32.8%), Intensity (19.7%), Duration (16.5%) as the dominant predictive
  features; age difference was not significant. HIGH confidence, peer-reviewed.
- **R7 — No validated decay formula exists for interpersonal ties specifically.** The
  Ebbinghaus forgetting curve / spaced-repetition half-life math is well-established for
  *memory retention* and is the evident inspiration for CRM-app "going cold" language, but no
  source found validates this math against real relationship data — it's a borrowed design
  metaphor everywhere it appears in relationship-management products. HIGH confidence on the
  memory-decay math itself; MEDIUM-HIGH on the absence claim.
- **R8 — Recency-windowed inference is the near-universal fix for co-occurrence staleness and
  CC-noise bias.** Microsoft Viva Insights restricts "active collaborators" to a rolling
  4-week window specifically because cumulative counts go stale (HIGH — official Microsoft
  docs). Christidis & Gomez Losada (MDPI, peer-reviewed, 2019) found email-based centrality
  metrics are "highly correlated with number of followers" — CC/broadcast recipients inflate
  apparent involvement independent of actual participation (HIGH confidence, though summarized
  via secondary search snippet rather than a full-paper read).
- **R9 — Community-detection algorithms (Louvain, ego-centered variants) are the standard
  technique for this exact clustering problem**, and ego-centered/local detection is the
  right variant for a single-user vantage point (MEDIUM — standard, well-documented
  algorithms). A specific "per-thread vs. contact-wide co-occurrence" fix for CC-noise was
  searched for directly and **not found** in any source — flagged as UNVERIFIED, not adopted
  as a v1 design (see rollout step 4).
