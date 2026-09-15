# Phase 0 Research: Social Cognition Co-Occurrence

No items in the plan's Technical Context are marked `NEEDS CLARIFICATION` — the
spec pins claim kinds, source weights, and the recency window verbatim, and the
existing Phase 57/124/125/128 code fixes language, framework, and storage. This
document resolves the design choices the spec explicitly deferred to plan time,
plus one correctness finding that changes the shape of the write path.

## Decision 1: Hypothesis formation and promotion MUST use different `SourceFunction`s

**Decision**: Co-occurrence hypothesis formation (`ClaimKind.INFERENCE`) submits
its `Contribution` with `source_function=SourceFunction.REFLECTION`. Promotion
to an identity edge (`ClaimKind.IDENTITY`) submits with
`source_function=SourceFunction.SOCIAL_COGNITION`.

**Rationale**: `core/contracts/ze-plugin/ze_plugin/contribution.py`'s `_LICENSE`
table is the actual gate the seam enforces:

```python
SourceFunction.SOCIAL_COGNITION: frozenset({ClaimKind.IDENTITY}),
SourceFunction.REFLECTION: frozenset({ClaimKind.INFERENCE, ClaimKind.SUSPICION}),
```

`SourceFunction.SOCIAL_COGNITION` is licensed for `ClaimKind.IDENTITY` **only**
— a hypothesis submitted under it with `claim_kind=INFERENCE` would be rejected
by `validate_and_submit()` before it ever reached the store. The spec's own
Verbatim Constraints name `SourceFunction.SOCIAL_COGNITION` for *promoted
identity edges* specifically, and FR-002 requires the hypothesis itself to be
`INFERENCE` — read together, these already imply two different source
functions; this decision just makes the mechanism explicit so the plan doesn't
accidentally collapse them into one call site. `SourceFunction.REFLECTION` is
the same function `ze_correlation.engine.CorrelationEngine` already uses for
its own (LLM-driven, ephemeral) hypotheses, so reusing it for the (deterministic,
persisted) co-occurrence hypothesis keeps one source function meaning "Ze formed
a belief about itself/the world," consistent with existing usage.

**Alternatives considered**:
- One `Contribution` call with `claim_kind` switched at promotion time —
  rejected: the seam has no "upgrade claim kind in place" operation: the
  hypothesis and the identity edge are different target rows
  (`correlation_hypothesis` vs. `memory_relationships`) written by different
  `write` callbacks, so two seam calls are already required; the only
  question this decision resolves is which `source_function` each one uses.
- Route both through `SourceFunction.EXECUTIVE` (licensed for `IDENTITY`,
  `FACT`, `INFERENCE`, `SUSPICION`, `PRIORITY` — a superset) — rejected: that
  license exists for the orchestration engine's own multi-kind decisions, not
  for a domain plugin's contributions, and would blur the seam's plugin-
  attribution story (collision detection groups by `(source_function,
  provenance)`; using `EXECUTIVE` for a plugin-owned write misattributes it).

## Decision 2: `SOURCE_WEIGHTS` and the co-occurrence algorithm stay in `ze-personal`, not `ze-correlation`

**Decision**: `ze-correlation` gains no new person/project-aware code. The
evidence-gathering, `SOURCE_WEIGHTS`-based scoring, and corroboration gate live
in a new `ze_personal/social/` subpackage. `ze-personal` reaches
`ze_correlation`'s `Hypothesis`/`EvidenceRef`/store types through a new
`ze_sdk.correlation` re-export module.

**Rationale**: Constitution III is explicit — `core/` packages carry no domain
knowledge, and `SOURCE_WEIGHTS` (`manual`/`conversation`/`email`/`calendar`/
`research`) is contact-domain vocabulary already owned by
`ze_personal.contacts.types`. `ze-correlation`'s `CorrelationEngine` is
deliberately generic (works over arbitrary `Entity` neighbourhoods via an LLM
call); teaching it what a "project" or a "reply vs. CC-only mention" means
would be exactly the domain leak the constitution forbids. The existing
precedent for a plugin needing a core cognition package's *types* without
importing `ze_core`/`ze_plugin` directly is `ze_sdk.memory`,
`ze_sdk.automation`, `ze_sdk.contribution` — each a thin re-export module in
`packages/ze-sdk/`. `ze_sdk.correlation` follows the identical shape rather
than inventing a new access pattern.

**Alternatives considered**:
- Add a `co_occurrence.py` module directly inside `ze-correlation` that knows
  about `SOURCE_WEIGHTS` — rejected: this is precisely the domain-knowledge
  leak Constitution III forbids into a `core/` package, and would make
  `ze-correlation` depend on contact-domain constants that can change
  independently of correlation's own release cadence.
- Give `ze-personal` a narrow direct dependency on `ze-correlation` (the
  precedent already used for `ze_memory.dream.store`, per the package
  dependency graph in `CLAUDE.md`) — rejected in favor of the SDK re-export:
  the `ze_memory.dream.store` exception is read-only and narrow (one journal
  read); this phase needs several `ze_correlation` symbols
  (`Hypothesis`, `EvidenceRef`, store methods) across multiple new files, which
  is exactly the shape `ze_sdk.*` modules exist to serve, and keeps the
  "plugins import only `ze_sdk.*`" rule uniform rather than adding a second
  ad-hoc exception.

## Decision 3: Corroboration threshold — 2 independent evidence items across 2 distinct days, mirroring dream promotion's shape

**Decision**: A hypothesis is corroborated when its evidence set contains at
least 2 items from **distinct** communication events (distinct thread/meeting
ids, not just distinct messages in the same thread) spanning at least 2
distinct calendar days within the 30-day window. A single user confirm
satisfies corroboration immediately regardless of evidence count.

**Rationale**: The spec's Assumptions section explicitly asks this to mirror
"dream/insight promotion's existing 'enough independent support' discipline."
`core/cognition/ze-memory/ze_memory/dream/promoter.py`'s `passes_support` gate
uses named, separately-checked thresholds — `support_count`,
`distinct_session_count`, `temporal_spread_days` — rather than a single opaque
number. This phase adopts the same *shape* (named, separately-checked
thresholds) scaled down for a two-endpoint pair instead of a promoted fact:
"2 independent events" plays the role of `support_count >= 2` (dream promotion
uses 3, but dream promotion corroborates a fact from freeform episodes across
the whole memory; here the pair is already known from the person+project graph
neighbourhood, a narrower and more precise search space, so a lower bar is
consistent with User Story 3's "wrong guesses must not become the directory"
concern being handled by the recency window + reply-vs-CC weighting, not by
raising the count alone). "2 distinct days" plays the role of
`distinct_session_count`/`temporal_spread_days` together — it is what
specifically rules out "a single CC-heavy broadcast" (SC-003): a broadcast is
one event on one day, so it can never satisfy "distinct events across distinct
days" on its own, independent of its weak `research`-tier weight.

**Alternatives considered**:
- A pure confidence-threshold gate (promote once the weighted score crosses a
  number) — rejected: a single high-weight event (e.g. one reply-heavy thread)
  could then promote from a single occurrence, which is exactly the
  "over-confident inference" risk User Story 3 names as the ADR's main product
  risk; requiring *distinct* events across *distinct* days is what specifically
  defeats a one-shot false positive.
- Match dream promotion's exact numbers (3 support / 2 sessions / 7-day
  spread) — rejected: those numbers are tuned for corroborating a *fact*
  synthesized from loose episodic recall; project membership evidence is
  already graph-anchored (a specific person, a specific project, real
  thread/meeting ids), a smaller, more targeted search space, so requiring 3
  independent recent contacts before Ze will even hedge "who seems to be on
  this" would understate real evidence the user can already see in their own
  inbox — the spec's SC-001 fixture is "a week of reply-and-meeting
  co-occurrence," which is 2 events easily.

## Decision 4: Corroboration and promotion run inside one new proactive job, not per-inflow

**Decision**: A new `SocialCooccurrenceJob` (`ze_personal/jobs/
social_cooccurrence.py`, `@proactive_job`) runs on the existing scheduler
cadence (daily, matching `ContactReview`/`InsightEngine`'s existing cadence
class). It re-scans the 30-day window for every known person↔project and
person↔person pair with any fresh evidence, updates or creates each pair's
`Hypothesis`, and promotes any that newly satisfy Decision 3's gate. It does
**not** hook into `ze_worldstate.inflow`'s per-message extractor path.

**Rationale**: FR-003's evidence weighting and Decision 3's "distinct events
across distinct days" gate are both properties of an *accumulated* evidence
set, not of one incoming message — computing them correctly requires re-
reading the whole rolling window on each check, which a batch job does
naturally and a per-message hook would have to simulate by re-querying anyway
(with no latency benefit, since corroboration is inherently multi-day). This
also matches Edge Case "if correlation is unavailable... this phase degrades
to 'no inferred memberships'" — a job that simply doesn't run this cycle
degrades cleanly, whereas a missed inflow hook on one email would need its own
backfill story. FR-001's "via `ze-correlation`... not a new correlation
package" is satisfied by the job calling into `ze_correlation`'s existing
`Hypothesis`/store/seam surface for every read and write; the job itself is
plugin-owned orchestration, not a second correlation engine.

**Alternatives considered**:
- Hook into `ze_worldstate.inflow.make_loop_extractor`-style per-message
  extension point — rejected: that hook is designed for one-shot loop
  proposals from a single message, not accumulating multi-day evidence sets
  per (person, project) pair; forcing it to also maintain rolling corroboration
  state per pair would duplicate the job's own bookkeeping inside a hot path.
- Reuse `ContactReview`'s existing job instead of adding a new one — rejected:
  `ContactReview` (per `plugin.py`'s `jobs()`) owns contact-confirmation review,
  a different lifecycle (pending → confirmed person rows) from co-occurrence
  hypotheses (which are never "pending" rows in `contacts` — they live in
  `correlation_hypothesis`); folding them into one job would mix two unrelated
  read models for no shared benefit.

## Decision 5: Promotion writes go through the seam; Phase 128's existing direct-extraction path is left as-is

**Decision**: `_write_relationship_edge_via_seam()` (new,
`ze_personal/graph/memory_hooks.py`) wraps the same entity-upsert +
`graph_store.upsert_relationship()` logic `_write_relationship_edge()` already
has, but as the `write` callback inside
`ze_sdk.contribution.submit_and_detect_collisions(contribution, write=...)`
with a `Contribution(claim_kind=IDENTITY, source_function=SOCIAL_COGNITION,
provenance=Provenance.SYNTHESIZED, ...)`. Phase 128's existing
`_write_relationship_edge()` (called from `contact_proposal_hook` for direct
LLM-extraction proposals) is **not** changed to go through the seam.

**Rationale**: Investigation of the current code
(`ze_personal/graph/memory_hooks.py`) found `_write_relationship_edge()` calls
`graph_store.upsert_relationship()` directly today, with no
`submit_and_detect_collisions` wrapper — unlike the parallel contact-write path
(`_write_contact_proposals`), which already goes through the seam via
`person_source_to_contribution()`. FR-006 requires *this phase's* promotion
path to go through the seam ("under `SourceFunction.SOCIAL_COGNITION`'s
existing identity license, going through the contribution seam"); it does not
ask this phase to retrofit Phase 128's direct-extraction writes, which are out
of this spec's scope (not named in Out of Scope, but also not named in any
User Story or FR — Phase 128 is a closed, shipped phase this spec only
*depends on*, not modifies). Reusing the entity-upsert half of the existing
function avoids duplicating the find-or-create logic while still giving this
phase's own writes real collision detection (FR-006's parenthetical).

**Alternatives considered**:
- Retrofit `_write_relationship_edge()` itself to always go through the seam,
  used by both paths — rejected as scope creep: it would silently change
  Phase 128's already-shipped, already-tested behavior (a `Contribution`
  argument would need to flow through `contact_proposal_hook` for every
  extraction-time edge write too), a change with its own test surface this
  spec does not ask for and that risks introducing collision-detection noise
  on a code path this phase has no acceptance scenario covering.

## Decision 6: Hedged conversational answers are a new tool, not the existing inline-correlation graph node

**Decision**: A new `@tool who_is_on_project(project_name: str)`
(`ze_personal/social/tools.py`) queries confirmed `WORKS_ON` edges from
`GraphStore` and separately queries unconfirmed, unpromoted hypotheses
referencing the same project entity (`HypothesisStore.list_by_entities`, new
method), and returns both sets distinctly labeled (confirmed vs. hedged-with-
evidence). This phase does **not** extend
`core/engine/ze-core/ze_core/orchestration/nodes/correlation.py`'s existing
`correlate()` node.

**Rationale**: That existing node calls `CorrelationEngine.correlate(seeds,
mode="inline")` — a live, ephemeral LLM call scoped to `research`/`news` agents
that produces `pattern`/`causal_guess`/`tension`/`convergence` hypotheses and
is never persisted. It has no concept of "membership" and no path to read
*stored* hypotheses at all — it generates new ones on every eligible turn. This
phase's hypotheses are the opposite: pre-computed, persisted, evidence-scored
over a 30-day window by the job (Decision 4), the thing a "who is on X" answer
needs to *read back*, not regenerate live. The spec's own Assumptions say to
reuse "existing correlation-surfacing **posture**" (hedge, cite evidence, don't
assert as fact) — a stylistic/behavioral constraint the new tool follows by
construction (confirmed and hedged results are never merged into one answer),
not a requirement to literally reuse the inline node's code path, which solves
a different problem (live pattern-finding vs. reading a stored membership
belief).

**Alternatives considered**:
- Extend `correlation.py`'s inline node to also pull stored co-occurrence
  hypotheses into its `components` output — rejected: that node is gated to
  specific agents (`research`, `news`) via `_DEFAULT_AGENTS`, runs on every
  eligible turn regardless of whether the user asked about a project, and its
  `_RELATION_LABELS` vocabulary (pattern/causal_guess/tension/convergence) has
  no "membership" concept — bending it to also do targeted, on-demand
  membership lookups would overload one node with two different jobs.
