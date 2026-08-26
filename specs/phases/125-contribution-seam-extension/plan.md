# Implementation Plan: Contribution Seam Extension — Social Cognition + Action

**Branch**: `125-contribution-seam-extension` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/phases/125-contribution-seam-extension/spec.md`

## Summary

Retrofit `Person`, `PersonSource`, `PersonRelationship`, and `ContactProposal`
(`plugins/ze-personal/ze_personal/contacts/types.py`) with `claim_kind` (fixed `IDENTITY`) and
typed `provenance`/`confidence` from `ze_agents.claims`, using a `_SOURCE_TYPE_TO_PROVENANCE`
mapping (research.md §1) and `DecayProfile.EVIDENCE_WEIGHTED` (research.md §2, per clarify
session). Add a new `packages/ze-sdk/ze_sdk/contribution.py` re-export of `Contribution`/
`EvidenceRef`/`SourceFunction`/`TargetFace`/`validate_and_submit` from `ze_plugin.contribution`
— required because `ze-personal` is a plugin, and CLAUDE.md's convention forbids plugin code
importing `ze_plugin.*` directly ("always go through `ze_sdk.*`"; Phase 124's three producers
were all core packages, exempt from this rule, so no such re-export existed yet). Add
`plugins/ze-personal/ze_personal/contacts/contribution.py` with
`person_source_to_contribution()`, importing from `ze_sdk.contribution` and mirroring
`ze_memory/contribution.py`'s `signal_to_contribution()` exactly, and wrap the two real
contact-store write boundaries — `consolidator.py::_store_candidate` and
`memory_hooks.py::_write_contact_proposals` — in Phase 124's `validate_and_submit()`,
matching/dedup logic itself untouched (FR-010). Flip
`_LICENSE[SourceFunction.SOCIAL_COGNITION]` from `frozenset()` to `frozenset({ClaimKind.IDENTITY})`
in `core/ze-plugin/ze_plugin/contribution.py` — the one core-package change this feature makes,
without which FR-004's rejection behavior is unenforceable. Backfill existing `contacts`/
`contact_sources`/`contact_relationships` rows via one new migration (`zc028`, chain tip
`zc027`). Retype `AgentResult.memory_proposals`/`.contact_proposals`
(`core/ze-agents/ze_agents/types.py`) as `list[ClaimBearingProposal]`, a new core-owned
`runtime_checkable` Protocol (mirroring the existing `LLMClient`/`DBPool` pattern) rather than
either concrete producer type or `Contribution` itself — both are unreachable from `ze-agents`
without inverting the package graph (research.md §3, discovered during this planning pass and
folded back into spec.md's FR-005). `record_trace` is untouched (FR-008); no cross-contribution
arbitration is built (FR-009).

## Technical Context

**Language/Version**: Python 3.11 (repo-wide `pyproject.toml` pin)

**Primary Dependencies**: No new third-party dependencies. `packages/ze-sdk` gains a new
`contribution.py` re-export module importing `ze_plugin.contribution` — `ze-sdk` already
depends on `ze-plugin` (package graph), so this is a new file, not a new dependency edge.
`plugins/ze-personal` gains an import of `ze_agents.claims` (already directly importable by
plugin code — only `ze_core.*`/`ze_plugin.*` are barred, per CLAUDE.md) and the new
`ze_sdk.contribution` module. `core/ze-agents/ze_agents/types.py` gains a `Protocol`
referencing only its own `ze_agents.claims` module — no new cross-package edge.
`core/ze-plugin/ze_plugin/contribution.py` gains one changed dict value — no new import.

**Storage**: PostgreSQL via `asyncpg`. One new migration on the `ze-personal`-owned `zc` chain
(tip `zc027`): `zc028_contacts_claim_kind.py`, adding `claim_kind TEXT NOT NULL` and
`provenance TEXT NOT NULL` (with backfill) to `contacts`, `contact_sources`, and
`contact_relationships` — see data-model.md's schema table and research.md §6. No other schema
changes.

**Testing**: pytest, `asyncio_mode = "auto"`. Modified tests in
`plugins/ze-personal/tests/contacts/test_consolidator.py` (rejection test mirroring Phase 124's
dream/correlation `test_contribution_write_path.py` pattern — FR-004/SC-001),
`test_store.py`/`test_person_store.py` (backfill migration behavior, FR-006), `test_extractors.py`
(new fields on constructed `ContactProposal`s, FR-001/FR-002). New
`plugins/ze-personal/tests/contacts/test_contribution.py` (`person_source_to_contribution()`
round-trip, mirroring `ze_memory/tests/test_contribution.py`). Modified
`core/ze-plugin/tests/test_contribution.py` (`_LICENSE[SOCIAL_COGNITION]` now accepts
`IDENTITY`, rejects everything else). Modified `core/ze-agents/tests/` for the new
`ClaimBearingProposal` Protocol and `AgentResult` field types. New
`packages/ze-sdk/tests/test_contribution.py` (re-export surface — imports resolve, `__all__`
matches). No real DB (mock asyncpg with `AsyncMock`), no real LLM.

**Target Platform**: Backend service packages (`ze-personal`, `ze-sdk`, `ze-plugin`,
`ze-agents`), wired transitively into `apps/ze-api`. No new deployment unit.

**Project Type**: Single project — modifications to three existing packages (`ze-personal`
plugin, `ze-plugin` core, `ze-agents` core) plus one new re-export module in an existing
package (`ze-sdk`). No new package.

**Performance Goals**: Not a hard target. `validate_and_submit()` adds at most one licensing
dict lookup per contact write (`IDENTITY` is never in `_EVIDENCE_REQUIRED_KINDS`, so no
evidence-existence lookups run) — negligible relative to the existing LLM extraction call and
DB round-trip it wraps.

**Constraints**: MUST NOT modify `ze_plugin.contribution.Contribution`'s shape or
`validate_and_submit()`'s logic (spec.md Assumptions) — only the `_LICENSE` table's
`SOCIAL_COGNITION` entry changes. MUST NOT change consolidator dedup/merge logic (FR-010). MUST
NOT wrap `record_trace` (FR-008). MUST NOT implement cross-contribution arbitration (FR-009).
MUST NOT give `core/ze-agents` a dependency on `ze-memory`, `ze-personal`, or `ze-plugin`
(Principle III) — resolved via the `ClaimBearingProposal` Protocol (research.md §3). MUST NOT
import `ze_plugin.*` directly from `ze-personal` (plugin code) — resolved via the new
`ze_sdk.contribution` re-export.

**Scale/Scope**: Single user; contact tables hold at most a few thousand rows — backfill
migration runs once, in-band, no batching needed (consistent with `zm016`/`zcor002` precedent).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Spec-First Development | Spec exists at `specs/phases/125-contribution-seam-extension/spec.md`, clarified (4 questions resolved across `/speckit-clarify` and this planning pass — see spec.md `## Clarifications`), status updates to `Planned` here and `Done` alongside implementation. | PASS |
| II. Single-User Model | No `user_id`, no multi-tenancy; contact tables and the `_LICENSE` table are process-global/single-user as today. | PASS |
| III. Layered Package Architecture | `ClaimKind`/`Provenance` remain the doctrine-mandated closed enums (unchanged, Phase 111). `PersonSource`/`Person`/`PersonRelationship`/`ContactProposal` stay `ze-personal`-owned domain types; `source_type` (plugin-owned inflow string) is untouched, `provenance` (the closed epistemic enum) is additive. `ze-agents` gains **zero** new cross-package import edges — the `ClaimBearingProposal` Protocol references only `ze_agents.claims` (research.md §3, data-model.md). `ze-personal` reaches `ze_plugin.contribution` only through the new `ze_sdk.contribution` re-export, per the "plugin code never imports `ze_plugin.*` directly" rule — matching how `ze-personal` already reaches `ze_communication` through `ze_sdk.channels`. `ze-plugin`'s `_LICENSE` edit is a doctrine-table update, not new domain knowledge in core. | PASS |
| IV. Typed, Explicit Python | All new/modified fields are dataclass fields in `types.py`; `ClaimBearingProposal` is a `Protocol` in `ze_agents/types.py`, matching the existing `LLMClient`/`DBPool` convention. No bare `Exception`/`ValueError` — rejections reuse Phase 124's `UnlicensedClaimKindError`. Async I/O unchanged. No module-level mutable globals (`_SOURCE_TYPE_TO_PROVENANCE`, `_LICENSE` are frozen module constants). | PASS |
| V. Test Discipline | New/modified tests listed under Testing above; no real DB (`AsyncMock`), no real LLM. `make test-personal`, `make test-plugin`, `make test-agents`, `make test-sdk`, `make lint` must all pass. | PASS |
| VI. Explicit Persistence | One hand-written raw-SQL Alembic migration (`zc028`) on the chain owned by `ze-personal` (the package owning `contacts`/`contact_sources`/`contact_relationships`), continuing the `zc` chain at `zc027`. No ORM. | PASS |
| VII. One LLM Gateway | No LLM call anywhere in this feature — a pure type/write-path retrofit over existing extraction output. | PASS |

No violations. Complexity Tracking section documents one accepted deviation from the spec's
originally-drafted FR-005 wording, resolved during planning (below), not a constitution
violation.

## Project Structure

### Documentation (this feature)

```text
specs/phases/125-contribution-seam-extension/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit-tasks — not created here)
```

No `contracts/` directory — this feature has no external interface (no new REST route, no new
WS frame shape, no new UI surface); it is an internal cross-package write-path retrofit,
consistent with the "skip if purely internal" guidance and Phase 124's precedent.

### Source Code (repository root)

```text
packages/ze-sdk/ze_sdk/
├── contribution.py          # NEW: re-exports Contribution, EvidenceRef, SourceFunction,
│                            #   TargetFace, validate_and_submit from ze_plugin.contribution
│                            #   (required so ze-personal, a plugin, never imports ze_plugin.*
│                            #   directly — CLAUDE.md convention)
└── tests/
    └── test_contribution.py    # NEW: re-export surface check

plugins/ze-personal/ze_personal/contacts/
├── types.py                # MODIFIED: Person, PersonSource, PersonRelationship,
│                            #   ContactProposal gain claim_kind/provenance; new
│                            #   _SOURCE_TYPE_TO_PROVENANCE mapping (FR-001, FR-002, research.md §1)
├── contribution.py         # NEW: person_source_to_contribution() (research.md §7),
│                            #   imports from ze_sdk.contribution
├── consolidator.py          # MODIFIED: _store_candidate wraps its store.upsert()/
│                            #   add_source() sequence in validate_and_submit() (FR-003, FR-004)
├── extractors.py            # MODIFIED: extract_email_contacts/extract_calendar_contacts
│                            #   populate the new ContactProposal fields (FR-001)
├── store.py                 # MODIFIED: _person_from_row/_source_from_row read
│                            #   claim_kind/provenance; upsert()/add_source()/add_relationship()/
│                            #   get_relationships() write and return the two new columns
│                            #   (FR-001, FR-002 — discovered while planning: these row-mapping
│                            #   and INSERT column lists don't use SELECT-* everywhere)
├── migrations/versions/
│   └── zc028_contacts_claim_kind.py   # NEW: claim_kind/provenance columns + backfill (FR-006)
└── tests/
    ├── test_contribution.py            # NEW (person_source_to_contribution round-trip)
    ├── test_consolidator.py            # MODIFIED (FR-004 rejection test, SC-001)
    ├── test_extractors.py              # MODIFIED (new field assertions)
    └── test_person_store.py            # MODIFIED (backfill/round-trip with new columns)

plugins/ze-personal/ze_personal/graph/
└── memory_hooks.py          # MODIFIED: _write_contact_proposals wraps its
                              #   upsert()/add_source() sequence in validate_and_submit() too
                              #   (FR-003's "same write boundary" — Edge Case parity with
                              #   consolidator.py, research.md §7)

core/ze-plugin/ze_plugin/
├── contribution.py          # MODIFIED: _LICENSE[SOCIAL_COGNITION] = frozenset({ClaimKind.IDENTITY})
│                            #   (research.md §5)
└── tests/
    └── test_contribution.py    # MODIFIED: SOCIAL_COGNITION licensing assertions

core/ze-agents/ze_agents/
└── types.py                  # MODIFIED: new ClaimBearingProposal Protocol;
                              #   AgentResult.memory_proposals/.contact_proposals retyped
                              #   list[ClaimBearingProposal] (FR-005, research.md §3)
```

**Structure Decision**: `plugins/ze-personal/ze_personal/contacts/contribution.py` holds only
`person_source_to_contribution()`, mirroring `ze_memory/contribution.py`/
`ze_worldstate/contribution.py`'s one-function-per-producer-package pattern exactly — the
conversion direction stays "producer package imports the shared `Contribution` type," never the
reverse; the only difference from those two precedents is the extra `ze_sdk.contribution`
re-export hop, required because `ze-personal` is a plugin and they are core packages.
`memory_hooks.py` (in `ze_personal/graph/`, not `contacts/`) is touched separately from
`consolidator.py` because it is a second, independent write boundary reaching the same
`PersonStore` (agent-turn-triggered contact proposals vs. episode-consolidation-triggered ones)
— both must be wrapped for FR-004's "any social-cognition-originated write" to hold, not just
the consolidator's. The `_SOURCE_TYPE_TO_PROVENANCE` mapping lives in `types.py` alongside the
types it maps (not `contribution.py`) so the backfill migration's Python-side
verification/tests can import it without importing the `ze_sdk`/`ze_plugin` dependency chain
`contribution.py` carries.

## Complexity Tracking

*One deviation from spec.md's originally-drafted FR-005, resolved during this planning pass and
already folded back into spec.md itself — not a live inconsistency, recorded here for
traceability.*

| Deviation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| `AgentResult.memory_proposals`/`.contact_proposals` typed against a new `ClaimBearingProposal` Protocol, not the concrete `ContactProposal`/`Fact`/`Contribution` types a literal reading of the spec's Input/Overview suggested | `core/ze-agents` sits below `ze-memory`, `ze-personal`, and `ze-plugin` in the package graph; importing any of their concrete types from `ze_agents/types.py` would invert the graph and violate Principle III ("core has no domain knowledge") | A literal `list[Contribution]` was rejected first (research.md §3 — `Contribution` has no content payload, would lose `.name`/`.classification`/etc. that `memory_hooks.py` reads today) and confirmed unreachable anyway (`ze-plugin → ze-agents`); a literal `list[ContactProposal]`/`list[Fact]` was the `/speckit-plan`-session-clarified resolution but is *also* unreachable (`ze-memory → ze-agents`, `ze-personal → ze-sdk → ze-agents`) — a structural `Protocol` (mirroring the existing `LLMClient`/`DBPool` pattern already used in this exact file) is the only typed option that doesn't require a new, graph-inverting import |
