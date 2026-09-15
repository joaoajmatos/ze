# Feature Specification: Social Cognition Co-Occurrence

**Feature Branch**: `130-social-cognition-co-occurrence`

**Created**: 2026-09-14

**Status**: Implemented

**Input**: User description: "Follow-up spec after Social Cognition Foundation (phase 128):
implement step 3 of specs/arch/social-cognition.md — project-person co-occurrence inference
via ze-correlation, using the 30-day recency window and SOURCE_WEIGHTS-based evidence
weighting already resolved in that brief, promoted to IDENTITY on corroboration. This is the
first genuinely new social-cognition capability; 128 was reconciliation. Step 4 of the ADR
(relationship-strength scores, user-settable cadence, per-thread membership) stays deferred."

**Governed by**: [`specs/arch/social-cognition.md`](../../arch/social-cognition.md) (rollout
step 3 only; steps 1–2 shipped as Phase 128; step 4 remains deferred) and, transitively,
[`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md) §The contribution model (social
cognition is licensed for `ClaimKind.IDENTITY` only; reflection may never emit a fact —
co-occurrence hypotheses are `INFERENCE` from `ze-correlation`, promoted to `IDENTITY` only
on corroboration) and [`specs/arch/claim-topology.md`](../../arch/claim-topology.md). Depends
on [`specs/phases/128-social-cognition-foundation/spec.md`](../128-social-cognition-foundation/spec.md)
(`project` entity, `WORKS_ON` / `COLLABORATES_WITH`, decaying `last_contact`) and
[`specs/phases/057-correlation-engine/spec.md`](../057-correlation-engine/spec.md) /
[`specs/phases/124-contribution-seam-core/spec.md`](../124-contribution-seam-core/spec.md)
(hypotheses as contributions; collision detection from Phase 126). Does not add a sixth
correlation subsystem, a relationship-strength score, or a project lifecycle state machine.

---

## Overview

Phase 128 put people and projects in the one memory graph and folded stale-follow-up nudges
into the shared attention budget. Edges in that graph still appear only when extraction
already named the link — a project mentioned next to a person, two people mentioned
together. This phase is the first *inference*: from communication that already happened
(email, calendar, conversation), Ze may conclude that a person probably works on a project
even when no extractor wrote `WORKS_ON` yet.

That conclusion is a hypothesis, not a fact. It is scored from recency-weighted evidence
inside a 30-day window, using the same source weights contacts already trust (a reply is
stronger than a CC-only mention). Until it is corroborated — repeated pattern, or the user
confirms — it stays an inference: visible if asked about, never asserted as settled
identity. Promotion writes a `WORKS_ON` (or `COLLABORATES_WITH`) edge under social
cognition's existing identity license. Wrong guesses from a distribution list must not
become "these people work together."

Projects still do not get `active` / `closed`. Who is "currently on this" is a fresh read
over the recency window. Stale collaborators fall out of that view without anyone formally
ending the project.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ze notices who is on a project from how they communicate (Priority: P1)

Over a few weeks the user emails and meets with the same people about the same named body
of work. Nobody said "Alice WORKS_ON Launch" as a fact. Ze still forms a hedged belief that
Alice is on Launch, grounded in those messages and meetings, and can answer "who seems to
be on Launch?" with that belief and its evidence — without treating it as a confirmed
relationship.

**Why this priority**: This is the only new capability in the social-cognition rollout.
Phase 128 made the graph able to *hold* the edge; this phase is how an unstated edge gets
proposed.

**Independent Test**: Feed a cluster of recent emails and calendar events that co-mention
a person and a project (replies, not only CC). Confirm a hypothesis exists linking them,
with evidence and a recency window, and that the memory graph does **not** yet have a
settled `WORKS_ON` edge. Ask Ze who is on the project; the answer is hedged and cites the
evidence.

**Acceptance Scenarios**:

1. **Given** repeated recent communication in which a known person and a known project
   co-occur as actual participation (replies or meetings, not only a CC list), **When**
   correlation runs, **Then** Ze holds an inference that the person works on the project,
   with evidence ids and a confidence that can decay.
2. **Given** that inference, **When** the user asks who is on the project, **Then** Ze
   answers in a hedged posture and shows why (which threads or meetings), and MUST NOT
   present it as a confirmed identity edge.
3. **Given** only a CC-only / no-reply mention in the same window, **When** correlation
   runs, **Then** that evidence is weighted at the weak (research-tier) source weight —
   it is not enough on its own to look like a settled collaboration.
4. **Given** communication older than the 30-day recency window, **When** correlation
   scores the hypothesis, **Then** that evidence does not count.

---

### User Story 2 - A corroborated pattern becomes a real graph edge (Priority: P1)

The same person-and-project pattern keeps showing up, or the user says "yes, Alice is on
Launch." Ze then writes a `WORKS_ON` edge in the memory graph — the same kind of edge
Phase 128 already extracts when someone names the link outright — with identity
provenance. Until that happens, nothing in `/brain/graph` looks like a confirmed
membership.

**Why this priority**: Promotion is what makes inference useful to every other reader of
the graph (priority, retrieval, the graph view) without violating "reflection never
emits a fact."

**Independent Test**: Drive a hypothesis past corroboration (repeated independent
evidence in the window, or an explicit user confirm). Query the graph from the person
and from the project; a `WORKS_ON` edge is there. A second hypothesis that was never
corroborated still has no identity edge.

**Acceptance Scenarios**:

1. **Given** an inference corroborated by repeated independent evidence inside the
   recency window, **When** promotion runs, **Then** a `WORKS_ON` edge exists in the
   memory graph under social cognition's identity license, and the hypothesis is no
   longer the only record of the link.
2. **Given** an inference the user confirms, **When** they confirm it, **Then** the same
   identity edge is written (mirroring how a pending contact becomes confirmed).
3. **Given** an inference that has not met corroboration and the user has not
   confirmed, **When** anyone reads the graph or a briefing, **Then** no settled
   `WORKS_ON` / `COLLABORATES_WITH` identity edge exists for that pair.
4. **Given** two people who keep actually participating together on a project (not
   merely CC'd), **When** promotion is justified, **Then** `COLLABORATES_WITH` MAY be
   written between those person entities in addition to each `WORKS_ON` — still only
   after corroboration.

---

### User Story 3 - Wrong or stale guesses do not become the directory (Priority: P2)

A large CC list once mentioned a project. Ze must not quietly add everyone as
collaborators. A person who used to be on a project and has not appeared in the window
must drop out of "who's currently on this" without Ze declaring the project closed.

**Why this priority**: The ADR's main product risk is creepiness from over-confident
inference. This story is the test that the promotion gate and the rolling window
actually protect the user.

**Independent Test**: (a) Ingest a single broadcast CC that names many people and a
project; confirm no identity edges and no unhedged surfacing. (b) Let a previously
promoted membership age beyond the recency window with no new participation; confirm
"who's currently on this" no longer lists them, while the project entity still exists.

**Acceptance Scenarios**:

1. **Given** a single CC-heavy broadcast and no replies from those recipients, **When**
   correlation and promotion run, **Then** Ze MUST NOT write identity `WORKS_ON` edges
   for those recipients and MUST NOT surface them as if they were on the project.
2. **Given** a promoted membership whose last participating evidence is older than the
   recency window, **When** the user (or a view) asks who is currently on the project,
   **Then** that person is not listed as current; the project entity is not marked
   closed or deleted.
3. **Given** an inference that later contradicts extracted evidence (user says they
   never worked together), **When** the user rejects or corrects it, **Then** it is
   not promoted, and any hedged mention stops treating it as likely.

---

### Edge Cases

- What happens if the project entity does not exist yet, only the person? Correlation
  MAY propose a project entity the same way Phase 128 extraction already upserts
  `project`, but MUST NOT promote an identity edge until both endpoints exist as graph
  entities.
- What happens if extraction already wrote `WORKS_ON`? Inference MUST NOT duplicate
  the edge; it MAY reinforce `last_contact` / confidence the same way Phase 128
  already reinforces named links.
- What happens if evidence spans two people and no named project? `COLLABORATES_WITH`
  MAY be hypothesized under the same window and weights; still `INFERENCE` until
  corroboration. No finer relationship taxonomy (friend vs colleague) is introduced.
- What happens when the daily attention budget is tight? Unconfirmed inferences MUST
  NOT spend interruption budget as if they were stale-follow-up identity nudges.
  Asking in conversation can still retrieve them.
- What happens if correlation is unavailable? Phase 128 extraction and PriorityView
  staleness continue; this phase degrades to "no inferred memberships," not to a
  second ad-hoc scorer.
- How does the system handle a person on many projects in the window? Each
  person–project pair is its own hypothesis. There is no cap invented here beyond
  correlation's existing bounded-hypothesis discipline.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST form project–person (and, where warranted, person–person)
  co-occurrence hypotheses from existing communication inflows (conversation, email,
  calendar) via `ze-correlation` — not via a new correlation package or a parallel
  social-graph store.
- **FR-002**: Those hypotheses MUST be `INFERENCE`-kind contributions. Social
  cognition MUST NOT write them as `FACT`. They MUST carry evidence ids and a
  decaying confidence.
- **FR-003**: Evidence outside a 30-day recency window MUST NOT count. The window
  MUST reuse the existing shared staleness helper and the same 30-day period other
  `TIME_LINEAR` jobs already use — no new per-social decay constant.
- **FR-004**: Evidence weighting MUST reuse contacts' existing `SOURCE_WEIGHTS`
  (`manual`/`conversation` = 1.0, `email` = 0.7, `calendar` = 0.6, `research` = 0.2).
  A same-thread reply is conversation-tier; a CC-only / no-reply mention is
  research-tier. System MUST NOT invent a separate CC-discount formula.
- **FR-005**: Until corroboration or explicit user confirm, the system MUST NOT
  write a `WORKS_ON` or `COLLABORATES_WITH` identity edge for that pair, and MUST
  NOT surface the hypothesis as settled membership in briefings, graph identity, or
  "who is on this project" answers.
- **FR-006**: On corroboration (repeated independent evidence in the window) or user
  confirm, the system MUST promote the link to an identity-kind `WORKS_ON` and/or
  `COLLABORATES_WITH` edge in the existing memory graph, under
  `SourceFunction.SOCIAL_COGNITION`'s existing identity license, going through the
  contribution seam (collision detection included).
- **FR-007**: "Who is currently on this project" MUST be computed from the recency
  window at read time. System MUST NOT add `active`/`closed` (or any other lifecycle
  state) on the project entity in this phase.
- **FR-008**: System MUST NOT introduce a continuous multi-factor relationship-strength
  score, a user-settable cadence field distinct from `last_contact`, or per-thread
  project-membership refinement. Those are ADR step 4, deferred.
- **FR-009**: System MUST NOT expand the person↔person predicate vocabulary beyond
  `COLLABORATES_WITH`. `Person.classification` remains the domain filter
  (personal / professional / unknown).
- **FR-010**: Unconfirmed inferences MUST NOT take shared attention-budget
  interruption slots. Phase 128's stale-follow-up source continues to rank confirmed /
  extracted relationships only.
- **FR-011**: This phase MUST NOT add a dedicated projects UI or a new REST collection
  for inferred memberships. Existing graph view and conversational ask are the read
  surfaces; hedged posture is required for unconfirmed inferences.

### Key Entities

- **Co-occurrence hypothesis**: A correlation hypothesis that person P participates in
  project R (and optionally that P collaborates with person Q), scored inside the
  30-day window with `SOURCE_WEIGHTS`. Claim kind `INFERENCE` until promotion.
- **Promoted membership**: A `WORKS_ON` or `COLLABORATES_WITH` memory-graph edge
  written only after corroboration or user confirm. Same shape as Phase 128 extracted
  edges (`confidence`, `last_contact`, provenance).
- **Current membership view**: A read-time slice of who still has participating
  evidence inside the recency window — not a stored list and not a project status
  field.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a week of reply-and-meeting co-occurrence between one person and
  one project, asking "who seems to be on [project]?" yields a hedged answer that
  cites at least one real piece of evidence, 100% of the time in the fixture — and
  the graph still has no identity `WORKS_ON` edge until corroboration or confirm.
- **SC-002**: After corroboration or user confirm, querying the graph from either
  endpoint returns the typed edge; a control pair that was only CC'd never gets that
  edge.
- **SC-003**: 0 identity `WORKS_ON` edges are written from a single CC-only broadcast
  fixture with no replies.
- **SC-004**: A person whose last participating evidence is older than 30 days is
  omitted from "currently on this project" while the project entity remains
  queryable — 100% of the time in the aged-membership fixture.
- **SC-005**: On a day when an unconfirmed co-occurrence hypothesis and a drifting
  loop both exist, the unconfirmed hypothesis never consumes the shared daily
  interruption budget.

## Assumptions

- Phase 128 has shipped: `project` entities, `WORKS_ON` / `COLLABORATES_WITH`,
  `last_contact`, dead `contact_relationships` gone, stale-follow-up on `PriorityView`.
- Corroboration threshold (how many independent pieces of evidence, across how many
  days) is a plan-time choice that SHOULD mirror dream/insight promotion's existing
  "enough independent support" discipline rather than invent a social-only rule.
  Exact numbers belong in the plan, not this spec.
- Inflows are the ones Phase 128 already uses (conversation, email, calendar). No new
  channel is required.
- Collision logging (Phase 126) applies automatically because promotion goes through
  the contribution seam; this phase does not build cross-function arbitration.
- Hedged conversational answers reuse existing correlation-surfacing posture (do not
  assert an inference as a fact), not a new speech-policy engine.

## Verbatim Constraints

Pinned by `specs/arch/social-cognition.md` rollout step 3 and the Phase 128 fence
this follow-up lifts:

- `WORKS_ON` — person → project identity edge after promotion
- `COLLABORATES_WITH` — person ↔ person identity edge after promotion
- `SOURCE_WEIGHTS` — `manual`/`conversation` = 1.0, `email` = 0.7, `calendar` = 0.6,
  `research` = 0.2
- 30-day recency window
- `ClaimKind.INFERENCE` on the hypothesis; `ClaimKind.IDENTITY` only after promotion
- `SourceFunction.SOCIAL_COGNITION` on promoted identity edges
- `list_stale_for_follow_up` / Phase 128 PriorityView source — unconfirmed inferences
  must not join it

## Out of Scope

- ADR step 4: relationship-strength score, user-settable cadence, per-thread
  membership refinement
- Project lifecycle (`active`/`closed`)
- Finer person↔person taxonomy than `COLLABORATES_WITH`
- New stores, new correlation engine, new attention budget
- Workspace run journal (Phase 129) — independent track
- Contribution *arbitration* (still gated on collision evidence from Phase 126)
