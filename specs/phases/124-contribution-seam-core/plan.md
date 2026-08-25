# Implementation Plan: Contribution Seam Core — Typed Proposals + Reflection Migration

**Branch**: `124-contribution-seam-core` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/124-contribution-seam-core/spec.md`

## Summary

Define a shared `Contribution` type (`claim_kind`, `provenance`, `confidence`, `target_face`,
`source_function`, `evidence`) in a new `core/ze-plugin/ze_plugin/contribution.py`, built on
the `ze_agents.claims` vocabulary from Phase 111, plus a single validation guard function
(`validate_and_submit()`) that checks a contribution's `claim_kind` against a doctrine-derived
per-function licensing table and its `evidence` references for presence and existence before
delegating to the caller's existing store write — never replacing it. Retrofit `Signal`
(`core/ze-memory`) with a new `provenance` field and a `signal_to_contribution()` conversion;
retrofit `OpenLoop`'s extraction path (`core/ze-worldstate`) with a `loop_to_contribution()`
conversion that maps its existing inflow-vocabulary `provenance` string onto the epistemic
`Provenance` enum (research.md §5). Both producers' real store-write call sites
(`ze_memory.retriever.ingest_signal`, `extraction.py`'s two `loop_store.create()` call sites) are
wrapped in `validate_and_submit()` too, per Edge Case 1's general (not reflection-specific)
licensing enforcement — matching/dedup and insert mechanics themselves stay unchanged, only a
licensing gate is added in front.
Migrate the dream pipeline's four `save_artifact()` call sites and the correlation engine's
`hypothesis_store.save()` call onto `validate_and_submit()`, always tagged `claim_kind` in
`{INFERENCE, SUSPICION}` — mechanically enforcing "reflection may never emit a fact"
(User Story 2, the feature's actual payoff) including for the `HINDSIGHT_FACT` artifact type,
whose name is a documented naming trap (research.md §6) that must never leak into its
`claim_kind` tag. No consumer of `signal_sources()` is rewired (FR-008); no cross-contribution
arbitration is built (FR-009).

## Technical Context

**Language/Version**: Python 3.11 (repo-wide `pyproject.toml` pin)

**Primary Dependencies**: No new third-party dependencies. `ze-plugin` gains an import of
`ze_agents.claims` and `ze_agents.errors` (both already used elsewhere in core packages —
no new dependency edge in the package graph). `core/ze-memory`, `core/ze-worldstate`,
`core/ze-correlation` each gain an import of `ze_plugin.contribution` (all three already
depend on `ze-plugin` transitively or directly — `ze-memory`/`ze-worldstate` are consumed by
`ze-plugin`-based plugins, and `ze-correlation → ze-worldstate`, so this is a new but
non-cyclic edge; confirmed no reverse dependency exists).

**Storage**: PostgreSQL via `asyncpg`. One new migration: `memory_signals` gains a
`provenance TEXT NOT NULL DEFAULT 'synthesized'` column (next free `zm` revision), then the
default is dropped so future inserts must set it explicitly — matching the Phase 111 `zm017`
backfill precedent (research.md §7). No other schema changes — `OpenLoop`, dream artifacts,
and `Hypothesis` already carry everything a correctly-typed `Contribution` needs.

**Testing**: pytest, `asyncio_mode = "auto"`. New tests in `core/ze-plugin/tests/test_contribution.py`
(licensing table, evidence validation, rejection logging — no DB, no LLM, pure function).
Modified/added tests in `core/ze-memory/tests/dream/`, `core/ze-worldstate/tests/`,
`core/ze-correlation/tests/` mock store Protocols with `AsyncMock`; the existence-check
callables `validate_and_submit()` takes are also mocked, never a real DB.

**Target Platform**: Backend service packages (`core/ze-plugin`, `core/ze-memory`,
`core/ze-worldstate`, `core/ze-correlation`), wired transitively into `apps/ze-api`. No
new deployment unit.

**Project Type**: Single project — modifications to four existing core packages plus one new
module in an existing package (`ze-plugin`). No new package.

**Performance Goals**: Not specified as a hard target in the spec; `validate_and_submit()`
must not measurably slow the dream pipeline's batch staging or correlation's inline hypothesis
save — it does at most one licensing dict lookup plus N evidence-existence lookups (N = size of
`evidence`, typically 2-5 per FR SC recall guarantee already enforced upstream in
`ze_correlation/engine.py`), no new LLM call, no new network round-trip beyond the existing
store call it wraps.

**Constraints**: Must not rewire `signal_sources()` consumers (FR-008). Must not add real
cross-contribution arbitration (FR-009). Must not replace the dream pipeline's promotion gate
(FR-010) — the seam validates shape/license only, promotion (NLI, critics) still runs after.
`ze-plugin` must not gain a dependency on `ze-memory`/`ze-worldstate`/`ze-correlation` (would
invert the package graph) — evidence-existence checks are injected as callables (research.md §8).

**Scale/Scope**: Single user; `evidence` lists are small (correlation's recall guarantee caps
around a handful of cited items per hypothesis); no pagination/indexing concerns.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Spec-First Development | Spec exists at `specs/phases/124-contribution-seam-core/spec.md`, clarified (2 questions resolved), status updates to `Planned` here and `Done` alongside implementation. | PASS |
| II. Single-User Model | No `user_id`, no multi-tenancy; `Contribution` and its licensing table are process-global. | PASS |
| III. Layered Package Architecture | `Contribution`, `SourceFunction`, `TargetFace` are core-owned closed enums per the doctrine-mandated-closed-set carve-out (research.md §2/§3) — not plugin-domain vocabulary, matching the precedent `ClaimKind`/`Provenance` set in Phase 111. `ze-plugin` (the seam's designated home per `contribution-seam.md`) gains the new module; no plugin imports `ze_core.*`; no `ze_plugin.*` direct import from plugin code (unaffected — plugins never touch this path, only `ze-memory`/`ze-worldstate`/`ze-correlation`, all core packages, do). | PASS |
| IV. Typed, Explicit Python | `Contribution`, `EvidenceRef` as dataclasses in `types.py`-equivalent (`contribution.py`, since it also holds the guard function — see Project Structure); `ContributionError` hierarchy as typed `ZeError` subclasses; `validate_and_submit()` is async; no module-level mutable state (the `_LICENSE` dict is a frozen module constant, not mutable). | PASS |
| V. Test Discipline | New `core/ze-plugin/tests/test_contribution.py` (pure function, no DB/LLM). Modified tests in three packages mock stores and the injected existence-check callables. `make test-plugin`, `make test-memory`, `make test-worldstate`, `make test-correlation`, `make lint` all must pass. | PASS |
| VI. Explicit Persistence | One hand-written raw-SQL Alembic migration on the `zm` chain (`core/ze-memory`, the package that owns `memory_signals`) adding `provenance`. No ORM. | PASS |
| VII. One LLM Gateway | No LLM call anywhere in this feature — `validate_and_submit()` is a pure/async guard over existing data, not a new generation step. | PASS |

No violations. Complexity Tracking section is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/phases/124-contribution-seam-core/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit-tasks — not created here)
```

No `contracts/` directory — this feature has no external interface (no new REST route, no new
WS frame shape); it is an internal cross-package write-path contract, consistent with the
"skip if purely internal" guidance.

### Source Code (repository root)

```text
core/ze-plugin/ze_plugin/
├── contribution.py         # NEW: Contribution, EvidenceRef, SourceFunction, TargetFace,
│                            #      _LICENSE table, ContributionError raising, validate_and_submit()
│                            #      (FR-001, FR-007, FR-009, FR-011, FR-012)
└── tests/
    └── test_contribution.py   # NEW

core/ze-agents/ze_agents/
└── errors.py                # MODIFIED: + ContributionError, UnlicensedClaimKindError,
                              #   MissingEvidenceError, DanglingEvidenceError (research.md §10)

core/ze-memory/ze_memory/
├── types.py                  # MODIFIED: Signal gains `provenance: Provenance` (FR-002)
├── contribution.py           # NEW: signal_to_contribution() (FR-003)
├── migrations/versions/
│   └── zm018_signal_provenance.py   # NEW: memory_signals.provenance column
├── retriever.py                # MODIFIED: ingest_signal()'s insert wrapped in
│                              #   validate_and_submit() (FR-003 amended, Edge Case 1)
├── dream/dream_pass.py        # MODIFIED: 4 save_artifact() call sites route through
│                              #   validate_and_submit(), claim_kind=INFERENCE always (FR-005)
└── tests/
    ├── test_contribution.py           # NEW (signal_to_contribution round-trip + ingest_signal
    │                              #   rejection test, Edge Case 1)
    └── dream/test_contribution_write_path.py   # NEW (FR-005 rejection + HINDSIGHT_FACT trap
                                   #   + promotion-gate non-regression, FR-010)

core/ze-worldstate/ze_worldstate/
├── contribution.py           # NEW: loop_to_contribution(), _INFLOW_TO_EPISTEMIC map (FR-004, research.md §5)
├── extraction.py              # MODIFIED: both loop_store.create() call sites
│                              #   (_create_declared_loop, propose_loop_candidates's gated path)
│                              #   wrapped in validate_and_submit() — matching/dedup mechanics
│                              #   themselves unchanged (FR-004 amended, Edge Case 1)
└── tests/
    └── test_contribution.py    # NEW (loop_to_contribution round-trip + rejection test)

core/ze-correlation/ze_correlation/
├── engine.py                  # MODIFIED: hypothesis_store.save() call wrapped in
│                              #   validate_and_submit() (FR-006), EvidenceRef projected
└── tests/
    └── test_contribution_write_path.py   # NEW (FR-006 rejection, identical validation logic to dream)
```

**Structure Decision**: `Contribution` and its guard function live together in one module
(`ze_plugin/contribution.py`) rather than split into `types.py` + a separate `seam.py`,
because the guard function has no state and no store dependency of its own (evidence checks
are injected) — splitting would add an import for no isolation benefit, and the whole module is
under 150 lines. Each retrofitted producer package gets its own small `contribution.py`
(`ze_memory`, `ze_worldstate`) holding only that package's conversion function — this avoids
`ze-plugin` depending on `ze-memory`'s `Signal` type or `ze-worldstate`'s `OpenLoop` type (which
would invert the package graph); the conversion direction is always "producer package imports
`ze_plugin.contribution.Contribution`," never the reverse. `ze-correlation`'s hypothesis save
doesn't need its own `contribution.py` — the projection from `Hypothesis.evidence` to
`contribution.EvidenceRef` is a two-line inline conversion at the one call site in `engine.py`,
not reused elsewhere, so a dedicated module would be premature (matches the "no premature
abstraction" guidance already governing this feature's own scope).

## Complexity Tracking

*No violations — table not needed.*
