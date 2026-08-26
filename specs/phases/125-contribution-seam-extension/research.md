# Research: Contribution Seam Extension — Social Cognition + Action

All items below were either resolved during `/speckit-clarify` (recorded in spec.md's
`## Clarifications`) or are planning-time details the spec explicitly delegates to this phase
(spec.md `## Assumptions`). No `NEEDS CLARIFICATION` markers remain in Technical Context.

## 1. `source_type` → `Provenance` mapping

**Decision**: A module-level `_SOURCE_TYPE_TO_PROVENANCE` dict in
`plugins/ze-personal/ze_personal/contacts/contribution.py`:

| `source_type` | `Provenance` | Rationale |
|---|---|---|
| `"manual"` | `PROMPT_SUPPLIED` | The user directly asserted this contact — same relationship as `LoopProvenance.USER_DECLARED → Provenance.PROMPT_SUPPLIED` in `ze_worldstate/contribution.py`. |
| `"conversation"` | `SYNTHESIZED` | An LLM extraction pass over conversation transcripts, not a direct external fetch — identical to `LoopProvenance.CONVERSATION → Provenance.SYNTHESIZED`, the exact same inflow name mapped the exact same way in the existing precedent. |
| `"email"` | `LIVE_SEARCH` | Read directly off a live Gmail API result (sender header) at extraction time — an external live fetch, not an LLM synthesis step. |
| `"calendar"` | `LIVE_SEARCH` | Read directly off a live Calendar API result (attendee list) — same reasoning as `"email"`. |
| `"research"` | `SYNTHESIZED` | The prospecting agent's browser-driven research draws an inferred conclusion about a person from browsing, not a direct read of one source record — matches its `SOURCE_WEIGHTS["research"] = 0.2`, the lowest-confidence, most-inferred tier. |

**Rationale**: Reuses the exact `_INFLOW_TO_EPISTEMIC`-dict pattern `ze_worldstate/contribution.py`
already established for `OpenLoop`, per `plugin-domain-vocabulary.md`'s ratified rule: the
closed `Provenance` enum stays exactly the doctrine's four epistemic values, and `source_type`
remains its own plain-string plugin-owned inflow field, untouched, alongside the new derived
`provenance` field — this is additive, not a replacement.

**Alternatives considered**: Mapping `"email"`/`"calendar"` to `GRAPH_RECALL` (rejected —
`GRAPH_RECALL` means retrieved from Ze's own memory graph, not a live external API read).

## 2. `DecayProfile` for identity-claim `Confidence`

**Decision**: `DecayProfile.EVIDENCE_WEIGHTED` (per `/speckit-clarify` session).

**Rationale**: The doctrine's identity-claim posture is "protected against churn... requires
repeated counter-evidence" (FR-007) — semantically an evidence-count relationship, not a
time-elapsed one, matching `EVIDENCE_WEIGHTED`'s `value * remaining_evidence / total_evidence`
shape rather than `TIME_LINEAR`'s periodic subtraction. No production code path calls `decay()`
on this value in this feature (FR-002/FR-007) — the field is populated correctly for whenever a
future decay job is wired in, exactly as `Hypothesis.confidence` sat un-decayed until
`HypothesisDecayJob` (Phase 111) was added later.

## 3. `AgentResult.memory_proposals` / `.contact_proposals` typing

**Decision** (per `/speckit-plan`-session clarification, refined below for layering): the
*concrete* proposal objects are `ContactProposal` (`ze-personal`, carrying `claim_kind`/
`provenance`/`confidence` directly per FR-001/FR-002) and `ze_memory.types.Fact` (`ze-memory`,
tagged `claim_kind=ClaimKind.FACT` at construction) — never a bare `Contribution`, and a
transient `Contribution` envelope is built only at each proposal's write boundary, never stored
on `AgentResult`. **However**, `AgentResult` lives in `core/ze-agents/ze_agents/types.py`, a
core package with zero dependency on `ze-memory` or `ze-personal` in the package graph
(`ze-memory → ze-agents`, `ze-personal → ze-sdk → ze-agents` — both depend on `ze-agents`, not
the reverse; `ze-agents` importing either concrete type would invert the graph and violate
Principle III, "core has no domain knowledge"). `ze_plugin.contribution.Contribution` itself is
equally unreachable (`ze-plugin → ze-agents`, not the reverse).

`AgentResult.memory_proposals`/`.contact_proposals` are therefore typed against a new
`runtime_checkable` **Protocol** defined in `ze_agents.types` itself (mirroring the existing
`LLMClient`/`DBPool` Protocol pattern already used in this exact package for the same reason —
referencing a shape without depending on its concrete implementation):

```python
@runtime_checkable
class ClaimBearingProposal(Protocol):
    claim_kind: ClaimKind
    provenance: Provenance
    confidence: float
```

`ClaimKind`/`Provenance` are safe to import — they live in `ze_agents.claims`, already inside
this same package, no new dependency edge. `AgentResult.memory_proposals: list[ClaimBearingProposal]`,
`contact_proposals: list[ClaimBearingProposal]` — real, checkable typing (not `list[Any]`), with
zero new cross-package import edges.

`ContactProposal` satisfies this Protocol structurally with no changes beyond the fields
FR-001/FR-002 already add to it (`claim_kind: ClaimKind`, `provenance: Provenance`,
`confidence: float` — types match the Protocol exactly). **`ze_memory.types.Fact` does *not*
currently satisfy this Protocol** — it has `confidence: float` but `provenance: str` (untyped)
and no `claim_kind` field at all; Phase 111's `zm016`/`zm017` retrofit added `claim_kind` only
as a `memory_facts` DB column (computed inline in `retriever.py`, never stored on the `Fact`
dataclass itself). Retrofitting `Fact` itself is out of this feature's scope — FR-001/FR-002
name only `Person`/`PersonRelationship`/`ContactProposal`/`PersonSource`, and `Fact` is used by
`extractor.py`/`projection.py`/`consolidation_store.py`/`retriever.py` well beyond this
feature's boundary. Since `memory_proposals` has zero current producers (confirmed by grep —
only the `field(default_factory=list)` declaration and read-only consumers in
`eval.py`/`schemas.py`; never populated), this feature types the field against
`ClaimBearingProposal` and leaves it unpopulated, same as today — the Protocol documents the
contract a *future* producer must satisfy (FR-005's "claim_kind set per originating proposal
type" becomes an obligation on that future producer, not a retrofit of `Fact` performed now).

**Rationale**: `ze_plugin.contribution.Contribution` is a metadata-only envelope with no content
payload, and spec.md's Assumptions bar modifying its shape ("reuses Phase 124's validated write
path... as-is; it does not modify or extend that mechanism's shape"). Every existing producer
(`Signal`, `OpenLoop`, dream artifacts) follows the same pattern: the domain type carries the
claim-vocabulary fields, and a `<producer>_to_contribution()` helper builds a `Contribution`
transiently, immediately consumed by `validate_and_submit()`. `contact_proposals` is actively
populated by `extract_email_contacts`/`extract_calendar_contacts`, which need their
`ContactProposal(...)` construction call sites updated to populate the three new fields (no
signature change needed — `ContactProposal` already accepts these as dataclass fields after
FR-001).

## 4. `target_face` for social-cognition contributions

**Decision**: `TargetFace.USER` for all `Person`/`PersonSource`/`PersonRelationship`/
`ContactProposal` contributions.

**Rationale**: `ze-doctrine.md`'s function-claim matrix lists social cognition's spine face as
"user-model, world-model"; `TargetFace` has no separate "world-model" member, and identity
claims about who someone is *to the user* are the user-model face by definition (a `Person`'s
`relationship_to_user` field is the concrete evidence of this). `TargetFace.WORLD` is reserved
for perception's world-model claims — reusing it for contacts would conflate two functions'
target faces the way `claim-topology.md` already warned against.

## 5. Updating `ze_plugin.contribution._LICENSE`

**Decision**: `_LICENSE[SourceFunction.SOCIAL_COGNITION]` changes from `frozenset()` to
`frozenset({ClaimKind.IDENTITY})` in `core/ze-plugin/ze_plugin/contribution.py`. No other
`_LICENSE` entries change — `SourceFunction.ACTION` stays `frozenset()` (per Decision 3 above,
action's proposal fields never construct a `Contribution` tagged `ACTION`; `record_trace` is
explicitly exempt per FR-008 and never enters the seam at all).

**Rationale**: FR-004 requires the write path to accept `IDENTITY` contributions from social
cognition and reject everything else — this is impossible without updating the shared licensing
table, since it currently licenses `SOCIAL_COGNITION` for nothing. This is the one core-package
(`ze-plugin`) change this feature makes; it is a one-line table edit, not a change to
`Contribution`'s shape or `validate_and_submit()`'s logic, consistent with the spec's
"registers a third caller" framing.

## 6. Migration ownership and structure

**Decision**: One new migration on the `zc` chain (owned by `ze-personal`, current tip `zc027`):
`zc028_contacts_claim_kind.py`, adding `claim_kind TEXT NOT NULL` and `provenance TEXT NOT NULL`
columns (with backfill `UPDATE`s, then `SET NOT NULL`) to all three existing contact tables —
`contacts` (`Person`), `contact_sources` (`PersonSource`), `contact_relationships`
(`PersonRelationship`) — mirroring the `zm016`/`zcor002` additive-column-plus-backfill pattern
exactly (`ALTER TABLE ... ADD COLUMN`, `UPDATE ... SET claim_kind = 'identity'` unconditionally
since `IDENTITY` is the only licensed kind, `UPDATE ... SET provenance = CASE source_type ...`
using Decision 1's mapping, then `ALTER COLUMN ... SET NOT NULL`).

**Rationale**: `ContactProposal` is never persisted directly (it's a transient extraction-result
type, never stored in a table of its own), so it needs no migration — only its two typed fields
on the dataclass. `Person`/`PersonSource`/`PersonRelationship` are all read from and written to
real tables (`store.py`), so all three need columns. This satisfies FR-006's backfill
requirement and spec.md's Assumptions ("No new Alembic migrations beyond adding
`claim_kind`/`provenance` columns... consistent with Phase 111's `zm016`/`zm017`/`zw001`-style
additive-column pattern").

## 7a. `ze_plugin.contribution` reaches `ze-personal` only via `ze_sdk`

**Decision**: Add `packages/ze-sdk/ze_sdk/contribution.py`, re-exporting `Contribution`,
`EvidenceRef`, `SourceFunction`, `TargetFace`, and `validate_and_submit` from
`ze_plugin.contribution` (mirroring `ze_sdk/channels.py`'s existing re-export-module pattern).
`ze-personal` imports from `ze_sdk.contribution`, never `ze_plugin.contribution` directly.

**Rationale**: CLAUDE.md's Imports convention is explicit: "Never import from `ze_plugin.*`
directly in plugin code — always go through `ze_sdk.*`; `ze_plugin` is for engine and SDK use
only." Phase 124's three retrofitted producers (`ze-memory`, `ze-worldstate`, `ze-correlation`)
are all `core/` packages, exempt from this rule, so this re-export path never needed to exist
before now — `ze-personal` is this feature's first `plugins/`-tier producer to join the seam.
`ze-sdk` already depends on `ze-plugin` in the package graph, so this is a new file, not a new
dependency edge. `ze_agents.claims` (`ClaimKind`/`Provenance`/`Confidence`/`DecayProfile`) needs
no re-export — plugin code already imports `ze_agents.*` directly today (e.g.
`ze_calendar/agents/calendar/agent.py`'s `from ze_agents.types import AgentContext, AgentResult`)
since only `ze_core.*`/`ze_plugin.*` are barred, not `ze_agents.*`.

## 7. Write-path wiring shape (mirrors Phase 124's `dream_pass.py`/`engine.py` pattern exactly)

**Decision**: `plugins/ze-personal/ze_personal/contacts/contribution.py` gains one conversion
helper, `person_source_to_contribution(source: PersonSource) -> Contribution`, mirroring
`signal_to_contribution()`/`loop_to_contribution()`. `consolidator.py::_store_candidate` and
`memory_hooks.py::_write_contact_proposals` both build a `PersonSource`, convert it via this
helper, and call `validate_and_submit(contribution, lambda: store-write-sequence)` — wrapping
the existing `store.upsert(person)` / `store.add_source(...)` calls exactly as
`dream_pass.py`/`extraction.py` wrapped theirs in Phase 124 (matching/dedup logic itself
untouched, per FR-010).

**Rationale**: `extractors.py` (`extract_email_contacts`/`extract_calendar_contacts`) never
calls the store directly — confirmed no `PersonStore`/`upsert` references in that file — so
FR-003's mention of "extractors" refers to `extractors.py`'s `ContactProposal` construction
gaining the new typed fields (Decision 3), not a second write-path call site; the only two real
write boundaries are `consolidator.py::_store_candidate` and
`memory_hooks.py::_write_contact_proposals`, both of which call `PersonStore.upsert()`/
`.add_source()` directly today.

## 8. No new error types

**Decision**: Reuse `UnlicensedClaimKindError`/`MissingEvidenceError`/`DanglingEvidenceError`
from `ze_agents.errors` as-is (already imported by `ze_plugin.contribution`). `IDENTITY` is not
in `_EVIDENCE_REQUIRED_KINDS` (`{INFERENCE, SUSPICION}`), so contact contributions never need
non-empty `evidence` — every call site passes `evidence=[]`, matching `OpenLoop`'s
`ACTIVE_CONCERNS`-face contributions.
