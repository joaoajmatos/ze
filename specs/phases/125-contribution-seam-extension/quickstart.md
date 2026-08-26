# Quickstart: Contribution Seam Extension — Social Cognition + Action

Validates the feature end-to-end: `Person`/`PersonSource`/`PersonRelationship`/`ContactProposal`
carry the shared claim vocabulary, the contact-store write path mechanically rejects any
`claim_kind` other than `IDENTITY`, existing rows are backfilled, and `AgentResult`'s proposal
fields are typed against the seam without inverting the package graph.

## Prerequisites

```bash
make install
make db-up
make migrate      # applies the new zc028 contacts claim_kind/provenance migration
```

## 1. `Person`/`PersonSource`/`PersonRelationship`/`ContactProposal` carry the vocabulary (User Story 1)

```bash
make test-personal -- -k "test_extractors or test_person_store"
```

Expected: a `ContactProposal` built by `extract_email_contacts`/`extract_calendar_contacts`
carries `claim_kind=IDENTITY`, a `Provenance` value matching `_SOURCE_TYPE_TO_PROVENANCE`'s
mapping for its `source_type` (research.md §1), and a `confidence` numeric value unchanged from
today's `SOURCE_WEIGHTS`-derived behavior. A `PersonSource` round-trips the same fields through
`PersonStore.add_source()`.

## 2. Contact-store writes enforce `IDENTITY`-only (User Story 2 — the payoff)

```bash
make test-plugin -- -k SOCIAL_COGNITION      # core/ze-plugin/tests/test_contribution.py
make test-personal -- -k test_consolidator   # FR-004 rejection test
```

Manual check (Python REPL, against a test DB session or `make dev-eval`):

```python
from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_sdk.contribution import Contribution, SourceFunction, TargetFace, validate_and_submit
from ze_agents.errors import UnlicensedClaimKindError

bad = Contribution(
    claim_kind=ClaimKind.FACT,          # a contact write mistagged FACT — must reject
    provenance=Provenance.SYNTHESIZED,
    confidence=Confidence(value=0.7, decay_profile=DecayProfile.EVIDENCE_WEIGHTED),
    target_face=TargetFace.USER,
    source_function=SourceFunction.SOCIAL_COGNITION,
    evidence=[],
)

async def write() -> None:
    raise AssertionError("should never run — rejected before this executes")

try:
    await validate_and_submit(bad, write)
    raise AssertionError("expected UnlicensedClaimKindError")
except UnlicensedClaimKindError:
    print("correctly rejected")
```

Expected: `UnlicensedClaimKindError` — `SOCIAL_COGNITION`'s license is now
`frozenset({ClaimKind.IDENTITY})`, so `FACT` is rejected before `write()` runs.

A correctly-tagged `claim_kind=ClaimKind.IDENTITY` contribution reaches `write()` and persists
exactly as `consolidator.py::_store_candidate`'s current direct `store.upsert(person)` call
would have (SC-001, Acceptance Scenario 1) — no behavior change for correctly-tagged writes.

## 3. Existing rows are backfilled (Edge Case, FR-006)

```bash
make migrate
psql "$DATABASE_URL" -c "SELECT claim_kind, provenance, source_type FROM contacts LIMIT 5;"
psql "$DATABASE_URL" -c "SELECT claim_kind, provenance, source_type FROM contact_sources LIMIT 5;"
```

Expected: every pre-existing row has `claim_kind = 'identity'` and a non-null `provenance`
derived from its own `source_type` via the same `_SOURCE_TYPE_TO_PROVENANCE` mapping new writes
use (research.md §6) — no row is left with `provenance IS NULL` after the migration's
`ALTER COLUMN ... SET NOT NULL` step.

## 4. `AgentResult` proposal fields are seam-typed without a graph inversion (User Story 3)

```bash
make test-agents -- -k ClaimBearingProposal
make lint   # confirms no forbidden ze-agents -> ze-memory/ze-personal/ze-plugin import edge
```

Manual check:

```python
from ze_agents.types import AgentResult, ClaimBearingProposal
from ze_personal.contacts.types import ContactProposal
from ze_agents.claims import ClaimKind, Provenance

proposal = ContactProposal(
    name="Ada Lovelace",
    source_type="email",
    claim_kind=ClaimKind.IDENTITY,
    provenance=Provenance.LIVE_SEARCH,
    confidence=0.7,
)
assert isinstance(proposal, ClaimBearingProposal)   # structural match — no inheritance needed

result = AgentResult(agent="messenger", response="", contact_proposals=[proposal])
assert result.contact_proposals[0].claim_kind == ClaimKind.IDENTITY
```

Expected: `ContactProposal` satisfies `ClaimBearingProposal` structurally (`runtime_checkable`
Protocol, no import of `ze_personal.*` inside `ze_agents/types.py`); `AgentResult.memory_proposals`
stays an empty `list[ClaimBearingProposal]` — no producer exists for it yet (research.md §3).

## 5. Regression check (SC-002)

```bash
make test-personal
make test-plugin
make test-agents
make lint
```

Expected: zero failures beyond the type-shape adaptations this feature itself introduces at
call boundaries — consolidation/extraction behavior (what gets proposed, dedup/merge resolution,
identity-claim decay posture) is unchanged.
