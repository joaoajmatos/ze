# Feature Specification: Claim Topology — Shared Confidence, Provenance, and Claim-Kind Vocabulary

**Feature Branch**: `111-claim-topology`

**Created**: 2026-07-27

**Status**: Draft

**Input**: User description: "Implement the shared claim topology proposed in specs/arch/claim-topology.md: a single ClaimKind/Provenance/Confidence vocabulary in core/ze-agents (ze_agents/claims.py), with a shared, parameterized confidence-decay function, retrofitted into the four existing claim producers — OpenLoop (core/ze-worldstate, becomes the reference/rename source), Hypothesis/EvidenceRef (core/ze-correlation, including fixing the currently-missing decay job so hypothesis confidence actually ages), memory_facts (core/ze-memory, replacing its bespoke -0.03/30-day linear decay with the shared decay profile), and Signal (core/ze-plugin, adding claim_kind and real confidence fields it currently lacks entirely, keeping magnitude as a separate relevance concept). Also extract the shared staleness-sweep utility duplicated across ze-worldstate and ze-automation into core/ze-proactive. No new tables; only add the missing claim_kind column to correlation_hypothesis and memory_facts via package-owned Alembic migrations. No consumer behavior changes beyond the decay fix."

**Governed by**: [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md) (constitutional — §The
epistemic ontology, §Belief revision), [`specs/arch/claim-topology.md`](../../arch/claim-topology.md)
(the design brief this feature implements), and
[`specs/arch/plugin-domain-vocabulary.md`](../../arch/plugin-domain-vocabulary.md) (constitutional
amendment — Principle III — that corrects `claim-topology.md`'s original `Provenance` design; see
Overview). Prerequisite for
[`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md)'s `Contribution` type and
[`specs/arch/attention-arbitration.md`](../../arch/attention-arbitration.md)'s `PriorityView`,
neither of which this feature builds.

---

## Overview

A 2026-07 architecture review mapped every reflective/proactive mechanism in the codebase
against the doctrine's epistemic ontology (identity/fact/inference/suspicion/priority claims,
each carrying honest provenance and a confidence that decays) and found the ontology
implemented **four times, four incompatible ways**, instead of once: `OpenLoop`
(`core/ze-worldstate`) has the only correct, complete implementation; `Signal`
(`core/ze-plugin`) has no confidence or claim-kind field at all; `Hypothesis`/`EvidenceRef`
(`core/ze-correlation`) has confidence but **no decay job**, so a correlation's confidence is
frozen forever at generation time — a live, direct violation of the doctrine's "everything
decays" rule; `memory_facts` (`core/ze-memory`) has a fourth, differently-shaped
provenance/confidence pair. Three independent modules also reimplement the identical "has this
gone stale" cutoff-check shape with no shared code.

This feature does not build new capability. It promotes `OpenLoop`'s already-correct
implementation to a shared vocabulary, retrofits the other three producers onto it, fixes the
frozen-hypothesis-confidence bug as a direct consequence, and extracts the duplicated
staleness-sweep shape into one helper. It is the type-and-decay layer the executive-function
work in `attention-arbitration.md` depends on — ranking claims from different producers on one
scale is not possible while they use four incompatible scales.

**Revision note**: `claim-topology.md`'s original design folded `ze-worldstate`'s five inflow
values (`conversation`, `email`, `calendar`, `ingestion`, `user_declared`) into the same closed
`Provenance` enum as the doctrine's four epistemic-origin categories. Two of those five —
`email`, `calendar` — are plugin domain vocabulary (`ze-messenger`, `ze-calendar`), not core
concepts; baking them into a core enum would require a `core/ze-agents` change every time a
future plugin adds its own inflow channel, violating Principle III. This spec was reworked
after `specs/arch/plugin-domain-vocabulary.md` (a constitutional amendment) resolved the
question: the doctrine-closed `Provenance` enum stays exactly the four epistemic categories
`ze-doctrine.md` actually defines; inflow-channel tagging becomes a separate, open-ended,
plugin-extensible string field, never a core enum. See FR-002 and FR-003 below.

---

## Clarifications

### Session 2026-07-27

- Q: Hypothesis's new decay job uses the TIME_LINEAR profile — what rate/window parameters should it use? → A: Reuse memory_facts' exact rate (-0.03/30-day, 0.50/0.25 cliff thresholds) — same parameters, not a separate tuned rate.
- Q: Should OpenLoop's own decay.py be refactored to call the new shared decay function (not just import the shared types)? → A: Yes — OpenLoop's decay.py calls the shared EVIDENCE_WEIGHTED decay function instead of keeping its own inline cascade math, so there is exactly one implementation of each profile.
- Q: How should the new Hypothesis decay job be scheduled/run? → A: New standalone proactive job in `ze-correlation`'s `jobs/` dir, registered on its own cadence like `ze-worldstate`'s existing sweep jobs — not folded into the push-sweep job.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A correlation's confidence ages like every other claim (Priority: P1)

Today, a correlation hypothesis is assigned a confidence value once, at generation time, and
that value never changes — even as the evidence it cited grows stale or gets contradicted
elsewhere in memory. This is the doctrine's clearest live violation: "everything decays" is a
stated rule, and one whole claim producer silently doesn't.

**Why this priority**: This is a correctness bug with user-visible consequences (a
months-old, uncorroborated hypothesis can still be pushed at full confidence), not a
speculative cleanup. It is also the cheapest single change to verify — a scheduled job either
runs and lowers stale confidence, or it doesn't.

**Independent Test**: Create a hypothesis, advance time past its decay window without new
corroborating evidence, run the decay sweep, and confirm its stored confidence has measurably
decreased and that a hypothesis whose confidence has decayed below the correlation engine's
existing push-bar threshold is no longer eligible for a push.

**Acceptance Scenarios**:

1. **Given** a `Hypothesis` created with confidence 0.8 and no further corroborating evidence,
   **When** the shared decay sweep runs after the hypothesis's decay window has elapsed,
   **Then** its stored confidence is lower than 0.8 and the decrease is recorded with the same
   auditability existing decay changes already have (e.g. an updated `confidence` column, no
   silent recomputation with no trace).
2. **Given** a `Hypothesis` whose confidence has decayed below the correlation push-bar's
   confidence threshold, **When** the push sweep next evaluates it, **Then** it is excluded from
   push eligibility on confidence grounds alone, exactly as a low-confidence hypothesis would be
   excluded today if it had started at that value.

---

### User Story 2 - Every claim producer speaks one vocabulary for kind and confidence; provenance stays doctrine-scoped (Priority: P2)

`Signal`, `Hypothesis`, `memory_facts`, and `OpenLoop` currently express "what kind of claim is
this, how sure are we" four different ways. Retrofitting all four onto one shared `ClaimKind` /
`Confidence` vocabulary means a future consumer (most concretely, `attention-arbitration.md`'s
`PriorityView`) can compare claims from any producer without a translation layer, and any new
producer has an obvious existing thing to reuse instead of inventing a fifth vocabulary.
`Provenance` — the doctrine's epistemic-origin axis (`graph_recall`/`live_search`/
`prompt_supplied`/`synthesized`) — unifies too, but only where a producer actually expresses
that axis (`EvidenceRef.origin`); it is not stretched to cover inflow-channel tagging
(conversation/email/calendar/ingestion), which stays a plugin-extensible string per
`specs/arch/plugin-domain-vocabulary.md`.

**Why this priority**: This is the structural fix the P1 bug is a symptom of. It is priority 2,
not priority 1, because it is a larger, slower-moving change (four call sites, two schema
migrations) whose value is mostly realized by future consumers rather than immediately.

**Independent Test**: For each of the four producers, confirm a claim it creates carries a
`claim_kind` drawn from the shared enum; for `Hypothesis`'s `EvidenceRef`, confirm `origin` is
drawn from the shared `Provenance` enum; for `OpenLoop`, confirm its inflow-channel field is a
plain string no longer validated against a closed core whitelist. Confirm existing call sites
and tests for each producer continue to pass unmodified except where the retrofit specifically
changed their type.

**Acceptance Scenarios**:

1. **Given** the shared vocabulary exists in `core/ze-agents`, **When** `ze-correlation`,
   `ze-memory`, and `ze-plugin` each import it, **Then** none of them gain a new package
   dependency they didn't already have (all three already depend on `ze-agents` directly or
   transitively).
2. **Given** an existing `OpenLoop` created before this feature ships, **When** the retrofit is
   applied, **Then** its stored `claim_kind` value is unchanged in meaning (a type promotion, not
   a data migration) and its stored inflow-channel value (previously typed `LoopProvenance`, now
   a plain `str`) is unchanged in both meaning and on-disk representation — only its type
   annotation and validation behavior change, per FR-003.
3. **Given** a `Signal` produced by any of the four current `SignalSource` implementers
   (calendar, finance, messenger, news), **When** this feature ships, **Then** the signal now
   carries a `claim_kind` (always `FACT`, perception's sole licensed claim-kind) and a real
   `confidence` distinct from its existing `magnitude` (relevance) field, and
   `ze-correlation`/`ze-worldstate` continue polling `signal_sources()` exactly as before — no
   consumer is rewired by this feature.
4. **Given** a hypothetical future plugin that produces `OpenLoop`s from its own inflow channel
   (e.g. a `ze-finance` sync), **When** it supplies a provenance string `ze-worldstate` has never
   seen before, **Then** the loop is created successfully — no `ValueError`, no core code change
   required — because the inflow-channel field is an unvalidated plugin-extensible string, not a
   closed enum membership check.

---

### User Story 3 - Staleness checks stop being reinvented per mechanism (Priority: P3)

`ze-worldstate`'s `stale_suspicion.py` and `drift.py` sweep, and `ze-automation`'s
`stuck_goals.py`, each independently implement the same "cutoff = now − window; if past it,
transition state" shape. A shared helper removes the duplication without touching what each
job does once it decides something is stale.

**Why this priority**: Lowest priority of the three — it is pure duplication removal with no
correctness bug attached (unlike P1) and no downstream consumer waiting on it (unlike P2). It
is included in this feature because it is small, mechanical, and shares the same "stop
reinventing per producer" motivation.

**Independent Test**: Confirm the three existing sweep jobs produce identical stale/not-stale
decisions before and after the extraction, for the same inputs.

**Acceptance Scenarios**:

1. **Given** the shared staleness helper exists in `core/ze-proactive`, **When**
   `stale_suspicion.py`, `drift.py`, and `stuck_goals.py` are each updated to call it, **Then**
   each job's own state-transition and window-configuration logic is unchanged — only the
   "is this past its cutoff" check is shared.

---

### Edge Cases

- What happens to `Hypothesis` and `memory_facts` rows that existed before this feature ships
  and have no `claim_kind` value? The migration must backfill a value for every existing row —
  it cannot leave the new column nullable-and-unset, since that would silently exempt old
  claims from the very posture rules this feature exists to enforce. See Assumptions for the
  backfill rule.
- What happens when a hypothesis's confidence decays below the floor confidence value already
  used elsewhere in the system (`OpenLoop`'s existing 0.05 floor)? Decay must never take a
  confidence to exactly zero or negative — it approaches the same floor `OpenLoop` already
  uses, for consistency.
- What happens if a claim's decay would change which claim-kind posture applies to it (e.g. a
  fact's confidence decays low enough that it should read more like a suspicion)? Out of scope
  for this feature — claim-kind and confidence remain independent fields; decay changes the
  confidence number, not the claim-kind. Any posture recomputation from confidence thresholds is
  a consumer-side concern (e.g. `attention-arbitration.md`), not this feature's.
- What happens to a `Signal` produced by a `SignalSource` implementer that does not yet know how
  to populate the new `confidence` field? The field is required, not optional — every
  implementer must supply a value at the point this feature ships, since a `Contribution`
  without a confidence is not a valid claim per the doctrine.
- What happens when a plugin supplies an `OpenLoop` inflow-channel string `ze-worldstate` has
  never seen before (not `conversation`, `ingestion`, or `user_declared`)? It is accepted and
  stored as-is — no core-side rejection, coercion, or whitelist check. Only `conversation` and
  `user_declared` trigger `ze-worldstate`'s own extraction fast-path logic; every other string
  (`email`, `calendar`, or a future plugin's own value) passes through as inert metadata, per
  `specs/arch/plugin-domain-vocabulary.md`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide one shared `ClaimKind` enumeration (`IDENTITY`, `FACT`,
  `INFERENCE`, `SUSPICION`, `PRIORITY`) in `core/ze-agents`, replacing `ze-worldstate`'s
  `LoopClaimKind` as the canonical definition.
- **FR-002**: The system MUST provide one shared, doctrine-closed `Provenance` enumeration in
  `core/ze-agents` covering exactly the doctrine's four epistemic-origin categories
  (`graph_recall`, `live_search`, `prompt_supplied`, `synthesized`) — no plugin-specific or
  inflow-specific values. Per `specs/arch/plugin-domain-vocabulary.md`, this enum MUST NOT gain
  a member naming a specific plugin, channel, or inflow mechanism (e.g. `email`, `calendar`);
  such values are a separate, open-ended concept covered by FR-003.
- **FR-003**: `OpenLoop.provenance` MUST change from the closed `LoopProvenance` enum (which
  today conflates the doctrine's epistemic-origin axis with plugin-owned inflow-channel values)
  to a plain `str` inflow-channel field. `ze-worldstate` MUST retain `LoopProvenance` as a
  namespace of string constants (`CONVERSATION`, `INGESTION`, `USER_DECLARED` — the three
  core-owned inflows its own extraction logic pattern-matches on today) so existing call sites
  using `LoopProvenance.CONVERSATION`/`LoopProvenance.USER_DECLARED` continue to work unchanged,
  but MUST NOT retain `EMAIL`/`CALENDAR` as declared constants (plugin-owned, and — per a repo
  audit — never pattern-matched anywhere outside their own declaration). `ze-worldstate` MUST
  NOT validate or coerce a plugin-supplied inflow string against a closed whitelist — the
  existing `LoopProvenance(provenance)` coercion in `propose_loop_candidates` (which raises
  `ValueError` for any unrecognized string) MUST be removed; any plugin may supply its own
  inflow string without a `ze-worldstate` code change.
- **FR-004**: The system MUST provide one shared `Confidence` value type in `core/ze-agents`
  carrying a `value: float` in `[0, 1]` and a `decay_profile` discriminator, plus one decay
  function parameterized by that profile — not a decay function per producer.
- **FR-005**: The decay function MUST support, at minimum, an `EVIDENCE_WEIGHTED` profile
  (matching `OpenLoop`'s existing evidence-retraction-cascade math, floor 0.05) and a
  `TIME_LINEAR` profile (matching `memory_facts`' existing -0.03/30-day math with its existing
  0.50/0.25 cliff behavior). No profile may represent "confidence that never decays" — every
  claim producer must select a real profile. `Hypothesis` MUST reuse the `TIME_LINEAR` profile's
  parameters exactly as `memory_facts` defines them (-0.03/30-day rate, 0.50/0.25 cliff
  thresholds) — not a separately tuned rate.
- **FR-006**: `OpenLoop` MUST be retrofitted to use the shared `ClaimKind` type for
  `claim_kind`. `LoopClaimKind` MUST remain importable from `ze-worldstate` as a re-export of the
  shared type, so existing call sites require no changes. (`OpenLoop.provenance`'s retrofit is
  covered separately by FR-003, since it changes type — enum to string — rather than being a
  transparent re-export.) `OpenLoop`'s `decay.py` MUST also be refactored to call the shared
  `EVIDENCE_WEIGHTED` decay function instead of keeping its own inline evidence-retraction-
  cascade math, so the `EVIDENCE_WEIGHTED` profile has exactly one implementation, consistent
  with SC-002/SC-003's "exactly one definition" bar.
- **FR-007**: `Hypothesis` MUST gain a `claim_kind` field, always `INFERENCE` or `SUSPICION`
  (never `FACT` — enforcing the doctrine's "reflection never emits a fact" rule at the type
  level for the first time on this producer). Classification rule (added post-`/speckit-analyze`
  — the original draft specified the field but not which of the two values a newly-generated
  hypothesis gets, E2): every hypothesis `CorrelationEngine` generates gets `SUSPICION` —
  `Hypothesis.narrative`'s own contract is "the reasoning, with uncertainty made explicit," which
  is `SUSPICION`'s definition ("a hedged, unconfirmed possibility"), not `INFERENCE`'s ("a derived
  conclusion"). No code path in this feature produces an `INFERENCE`-kind `Hypothesis`; the value
  exists on the enum for a future producer with an actual corroboration signal to draw on.
- **FR-008**: `EvidenceRef.origin` MUST be replaced with the shared, doctrine-closed
  `Provenance` type, adding the previously-missing `SYNTHESIZED` value to what correlation
  evidence can express. This is the correct fit for the closed enum (not a plugin/inflow
  concept) — `EvidenceRef.origin` describes how a piece of evidence entered the correlation
  engine's reasoning (recalled, searched, supplied, synthesized), exactly the doctrine's
  epistemic-origin axis FR-002 defines.
- **FR-009**: `Hypothesis` MUST gain a scheduled decay job using the shared `TIME_LINEAR`
  profile, so a hypothesis's confidence measurably decreases over time absent new corroborating
  evidence. This fixes the frozen-confidence gap described in User Story 1. The job MUST be a new
  standalone scheduled job in `ze-correlation`'s `jobs/` dir, registered on its own cadence —
  matching the existing pattern of `ze-worldstate`'s `DriftSweepJob`/`PushSweepJob` — rather than
  folded into the existing push-eligibility sweep.
- **FR-010**: `memory_facts` MUST gain a `claim_kind` column, and the dream pipeline's existing
  distinction between raw-observed and synthesized-uncorroborated rows MUST determine its value
  at write time (`FACT` for raw/observed rows and corroborated synthesized rows already promoted
  by the dream pipeline's existing gate; `INFERENCE` for uncorroborated synthesized rows).
- **FR-011**: `memory_facts`' existing bespoke decay implementation in the dream pipeline's
  `promoter.py` MUST be replaced by a call to the shared `TIME_LINEAR` decay function, preserving
  its existing -0.03/30-day rate and 0.50/0.25 cliff thresholds exactly — this is a
  reimplementation-removal, not a behavior change.
- **FR-012**: `Signal` MUST gain a `claim_kind` field, always `FACT` (perception's sole licensed
  claim-kind per the doctrine's contribution model), and a `confidence` field distinct from its
  existing `magnitude` field. `magnitude` (relevance) MUST NOT be renamed, merged into, or
  conflated with `confidence` — they remain two separate concepts. `Signal` gains no
  `provenance` field in this feature — its plugin source is already identified by its existing
  `source: str` field, which is itself an example of the plugin-owned-string pattern FR-003
  extends to `OpenLoop`.
- **FR-013**: All four `SignalSource` implementers (`ze-calendar`, `ze-finance`,
  `ze-messenger`, `ze-news`) MUST be updated to populate the new `claim_kind` and `confidence`
  fields when constructing a `Signal`.
- **FR-014**: The `SignalSource` Protocol itself, and how `ze-correlation` and `ze-worldstate`
  consume signals (polling `signal_sources()`), MUST NOT change. Only the shape of the object
  returned changes.
- **FR-015**: The system MUST provide one shared staleness-check helper in `core/ze-proactive`
  implementing the "cutoff = now − window; past it → stale" decision, and `ze-worldstate`'s
  `stale_suspicion.py` and `drift.py` sweep and `ze-automation`'s `stuck_goals.py` MUST each be
  updated to call it for their staleness check, while retaining their own distinct
  state-transition logic and window configuration unchanged.
- **FR-016**: The system MUST add a `claim_kind` column to `correlation_hypothesis`
  (`core/ze-correlation`, package-owned migration, `zcor` prefix) and to `memory_facts`
  (`core/ze-memory`, package-owned migration, `zm` prefix), each as a required (non-nullable)
  column with a migration-time backfill for existing rows — no existing row may be left without
  a `claim_kind`.
- **FR-017**: This feature MUST NOT introduce a `Contribution` type, an arbitration mechanism,
  or any change to which package depends on which — `specs/arch/contribution-seam.md`'s
  `Contribution` type remains a separate, later feature building on this one.
- **FR-018**: This feature MUST NOT change any surfacing, push-gating, or inline-mention
  behavior for `OpenLoop`, `Signal`, or `memory_facts` — only `Hypothesis` gains a behavior
  change (decay), and that change is additive (a previously-frozen value now moves), not a
  change to any gating logic that reads it. `OpenLoop.provenance`'s type change (FR-003) is a
  type-and-validation change, not a behavior change — stored values, and every existing
  comparison against `LoopProvenance.CONVERSATION`/`LoopProvenance.USER_DECLARED`, are
  unaffected.

### Key Entities

- **`ClaimKind`**: what kind of claim something is — identity, fact, inference, suspicion, or
  priority. Determines which posture (asserted vs. hedged vs. offered-as-a-question) a claim may
  be surfaced with, per the doctrine.
- **`Provenance`**: the doctrine's closed epistemic-origin vocabulary — graph recall, live
  search, prompt-supplied, or synthesized. Describes *how a claim entered reasoning*, tagged
  honestly at the source, per the doctrine. Deliberately closed at exactly these four values —
  see `specs/arch/plugin-domain-vocabulary.md`.
- **Inflow channel** (not a `ClaimKind`/`Provenance`/`Confidence` type — a separate, informal
  concept): which mechanism or plugin produced a claim (conversation, email, calendar,
  ingestion, user-declared, or a future plugin's own value). Always a plain string, owned and
  defined by whichever core module or plugin produces it, never a closed core enum. `OpenLoop`
  is this feature's one producer that carries this concept (its `provenance` field, despite the
  name, has always been inflow-channel data, not doctrine `Provenance` — see FR-003).
- **`Confidence`**: how sure a claim is and how fast that certainty ages — a float value plus a
  decay profile, with one shared decay function instead of one per producer.
- **`OpenLoop`, `Hypothesis`, `memory_facts` row, `Signal`**: the four existing claim producers
  this feature retrofits onto the shared vocabulary; no new entity is introduced for any of
  them.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A hypothesis with no new corroborating evidence has a measurably lower stored
  confidence value after its decay window elapses and the decay sweep runs, where before this
  feature its confidence never changed after creation.
- **SC-002**: Every one of the four claim producers (`OpenLoop`, `Hypothesis`, `memory_facts`,
  `Signal`) expresses claim-kind using the same shared `ClaimKind` enumeration — verified by
  there being exactly one definition of `ClaimKind` in the codebase, with the other three call
  sites importing rather than redefining it. The doctrine-closed `Provenance` enumeration has
  exactly one definition and is used exactly where the doctrine's epistemic-origin axis applies
  in this feature (`EvidenceRef.origin`) — verified by there being no second definition and no
  plugin-specific or inflow-specific member ever added to it (`specs/arch/plugin-domain-vocabulary.md`).
- **SC-003**: The three independently-implemented staleness cutoff checks are replaced by calls
  to one shared helper, verified by there being exactly one implementation of the
  cutoff-comparison logic in the codebase.
- **SC-004**: No existing test for `OpenLoop`, `Signal`, `Hypothesis`, `memory_facts`, or any of
  the three staleness-sweep jobs fails as a result of this feature, except tests specifically
  updated to assert the new fields/behavior this feature adds.
- **SC-005**: No new package dependency edge is introduced — every package that needs the shared
  vocabulary (`ze-worldstate`, `ze-correlation`, `ze-memory`, `ze-plugin`) already depends on
  `ze-agents` before this feature ships.
- **SC-006**: Every existing row in `correlation_hypothesis` and `memory_facts` has a non-null
  `claim_kind` value immediately after migration — zero rows are left in an unclassified state.

## Assumptions

- **Decay profile scope**: only `EVIDENCE_WEIGHTED` and `TIME_LINEAR` are built now, reusing
  `OpenLoop`'s and `memory_facts`' existing math exactly rather than inventing new decay
  behavior. `Hypothesis` uses `TIME_LINEAR` with `memory_facts`' exact parameters (closest
  existing precedent for a claim with no prior evidence-cascade concept; see FR-005).
- **Migration order**: `Hypothesis`'s decay job is implemented first, since it fixes a live bug
  and is independently verifiable; `memory_facts`' decay-function swap and `Signal`'s field
  additions follow; `OpenLoop`'s type rename/re-export and its `decay.py` refactor onto the
  shared `EVIDENCE_WEIGHTED` function (see FR-006) can happen at any point since neither changes
  anything observable.
- **Backward compatibility**: `LoopClaimKind` becomes a re-export of the shared `ClaimKind` type
  (per FR-006) rather than requiring every `ze-worldstate` call site to be rewritten in this
  feature — consistent with this repo's existing "wrap before replace" pattern. `LoopProvenance`
  cannot follow the same re-export path, since its shape is changing (closed enum → plugin-
  extensible string, per FR-003) — but a repo-wide audit found only two of its five values
  (`CONVERSATION`, `USER_DECLARED`) are ever pattern-matched anywhere outside their own
  declaration, so `LoopProvenance` is retained as a plain string-constant namespace exposing
  those two (plus `INGESTION`) as attributes, keeping every existing `LoopProvenance.CONVERSATION`
  /`LoopProvenance.USER_DECLARED` call site (production and test) working unchanged, while
  dropping `EMAIL`/`CALENDAR` as declared core constants and removing the closed-whitelist
  coercion in `propose_loop_candidates`.
- **Backfill rule for existing rows**: `correlation_hypothesis` rows backfill to `INFERENCE`
  (no corroboration signal exists today to distinguish `SUSPICION`); `memory_facts` rows
  backfill using their existing `provenance`/`corroborated` fields per FR-010's rule, since that
  distinction already exists in the dream pipeline's promotion logic.
- **No UI changes**: this feature is entirely backend/type-layer; no web UI surface is expected
  to change as a result of it shipping.
- **Single-user model**: consistent with the constitution — no per-user scoping concerns apply
  to a shared vocabulary type.
- **This feature does not resolve confidence calibration** (LLM self-rating vs. corroboration
  count vs. feedback) — that remains a separate, unresolved doctrine question. This feature
  standardizes the *shape* confidence values take and how they age, not *how a producer decides*
  what confidence value to assign initially.
</content>
