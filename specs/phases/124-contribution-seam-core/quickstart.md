# Quickstart: Contribution Seam Core

Validates the feature end-to-end: the shared `Contribution` type exists, `Signal`/`OpenLoop`
wrap into it and enforce licensing at their real write paths, and the dream/correlation write
paths mechanically reject `claim_kind=FACT`.

## Prerequisites

```bash
make install
make db-up
make migrate      # applies the new zm018 provenance migration
```

## 1. `Contribution` type + licensing table (User Story 1)

```bash
make test-plugin   # core/ze-plugin/tests/test_contribution.py
make test-memory test-worldstate   # includes Edge Case 1 rejection tests, see §2
```

Expected: `Contribution` round-trips from both a `Signal` and an `OpenLoop`; `magnitude` and
`confidence` remain distinct fields on the `Signal`-derived contribution (SC-003).

## 2. General licensing enforcement at `Signal`/`OpenLoop`'s real write paths (Edge Case 1)

```bash
pytest core/ze-memory/tests/test_contribution.py -k ingest_signal
pytest core/ze-worldstate/tests/test_contribution.py -k extraction
```

Expected: a `Signal` mistagged with a `claim_kind` other than `FACT` is rejected by
`ingest_signal()` before the `INSERT INTO memory_signals` runs; an `OpenLoop` candidate tagged
with a `claim_kind` outside `EXECUTIVE`'s license is rejected by `extraction.py`'s write path
before `loop_store.create()` runs — proving the licensing check is general-purpose, not
reflection-specific.

## 3. Reflection cannot submit a fact (User Story 2 — the payoff)

```bash
make test-memory        # core/ze-memory/tests/dream/test_contribution_write_path.py
make test-correlation   # core/ze-correlation/tests/test_contribution_write_path.py
```

Manual check (Python REPL, after `make dev-eval` is running or directly against a test DB
session):

```python
from ze_agents.claims import ClaimKind, Confidence, DecayProfile
from ze_plugin.contribution import Contribution, SourceFunction, TargetFace, validate_and_submit
from ze_agents.errors import UnlicensedClaimKindError

bad = Contribution(
    claim_kind=ClaimKind.FACT,          # dream pipeline tagging a fact — must reject
    provenance=...,
    confidence=Confidence(value=0.5, decay_profile=DecayProfile.TIME_LINEAR),
    target_face=TargetFace.SELF,
    source_function=SourceFunction.REFLECTION,
    evidence=[...],
)

try:
    await validate_and_submit(bad, write=lambda: dream_store.save_artifact(...))
    assert False, "should have rejected"
except UnlicensedClaimKindError:
    pass  # expected — SC-001
```

Expected: the rejection raises before `dream_store.save_artifact` is ever called (no row
inserted), and a `contribution_rejected` WARNING log line is emitted (`reason=unlicensed_claim_kind`).

Repeat with `claim_kind=ClaimKind.INFERENCE` on the same artifact — expect success, artifact
persisted exactly as before this feature (Acceptance Scenario 2), and confirm the existing
promotion gate (`gates.py`/`promoter.py`) still runs on it afterward (FR-010).

## 4. `HINDSIGHT_FACT` naming-trap regression test

```bash
pytest core/ze-memory/tests/dream/test_contribution_write_path.py -k hindsight_fact
```

Expected: an `ArtifactType.HINDSIGHT_FACT` artifact submitted with `claim_kind=INFERENCE`
succeeds; the same artifact type submitted with `claim_kind=FACT` (simulating an implementer
mistake mapping the artifact-type name to the claim-kind tag) is rejected — proves the artifact
type label never leaks into the licensing check (research.md §6).

## 5. No regression for existing consumers (User Story 3)

```bash
make test-correlation
make test-worldstate
```

Expected: all pre-existing assertions pass unchanged beyond call-boundary type-shape
adaptations (`signal_to_contribution`/`loop_to_contribution` wrapping) — SC-002.

## 6. Evidence existence validation (dangling reference)

```bash
pytest core/ze-plugin/tests/test_contribution.py -k evidence
```

Expected: a `SUSPICION`-kind contribution citing a nonexistent fact ID raises
`DanglingEvidenceError`; the same contribution with `evidence=[]` raises `MissingEvidenceError`
before the existence check is ever attempted (FR-011).

## Full suite

```bash
make lint
make test-plugin test-memory test-worldstate test-correlation
```
