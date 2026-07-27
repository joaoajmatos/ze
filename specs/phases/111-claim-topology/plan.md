# Implementation Plan: Claim Topology — Shared Confidence, Provenance, and Claim-Kind Vocabulary

**Branch**: `111-claim-topology` | **Date**: 2026-07-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/phases/111-claim-topology/spec.md`

## Summary

Four claim producers (`OpenLoop`, `Hypothesis`/`EvidenceRef`, `memory_facts`, `Signal`) each
express claim-kind, provenance, and confidence-with-decay a different way; `Hypothesis`'s
confidence never decays at all — a live doctrine violation. This feature promotes `OpenLoop`'s
already-correct implementation into a shared `ClaimKind`/`Confidence` vocabulary plus one
parameterized decay function in `core/ze-agents/ze_agents/claims.py`, retrofits the other three
producers onto it (fixing the frozen-hypothesis-confidence bug as a direct consequence via a new
scheduled decay job), and extracts the duplicated staleness-cutoff check from three sweep jobs
into one helper in `core/ze-proactive`. `Provenance` unifies too, but stays doctrine-closed at
exactly four epistemic-origin values (`graph_recall`/`live_search`/`prompt_supplied`/
`synthesized`) per `specs/arch/plugin-domain-vocabulary.md` — a constitutional amendment adopted
mid-design after review found the original brief would have baked plugin-owned inflow vocabulary
(`email`, `calendar`) into a core enum. `OpenLoop`'s inflow-channel field (previously mislabeled
`provenance`) becomes a plain, plugin-extensible string instead. No new tables — only two
required, backfilled `claim_kind` columns. No consumer-facing behavior change beyond the decay
fix and the inflow-channel validation removal (additive: previously-rejected plugin strings now
succeed).

## Technical Context

**Language/Version**: Python 3.12 (matches this repo's existing packages; `StrEnum` used
throughout, requires 3.11+)

**Primary Dependencies**: none new — reuses `ze-agents` (already the shared dependency of all
four producer packages, research.md §9), `ze-proactive`'s `@proactive_job` decorator (already
used by every sweep job this feature touches), `asyncpg` (existing driver, no ORM)

**Storage**: PostgreSQL — two additive, backfilled, non-nullable columns
(`correlation_hypothesis.claim_kind`, `memory_facts.claim_kind`); no new tables, no dropped
columns

**Testing**: pytest, `asyncio_mode = "auto"`; `AsyncMock` for asyncpg pools (no real DB in unit
tests, per `CLAUDE.md`); per-package `make test-<name>` targets
(`test-worldstate`, `test-correlation`, `test-memory`, `test-plugin`, `test-proactive`,
`test-automation`)

**Target Platform**: same backend service (FastAPI/LangGraph, Linux server) — no platform change

**Project Type**: internal type/infrastructure layer inside an existing monorepo (not a new
project or service)

**Performance Goals**: N/A — no throughput/latency target changes; the one behavior change
(`Hypothesis` decay job) runs on a low-frequency schedule against a single-user's bounded
hypothesis count, same profile as the existing `CorrelationJob`/sweep jobs it sits beside

**Constraints**: single-user scale throughout (research.md §7's SQL→Python cutoff-filtering
move is safe specifically because `open_loops`/`goals`/`correlation_hypothesis` never grow past
a few hundred rows for one user); zero new package dependency edges (SC-005, research.md §9)

**Scale/Scope**: 4 producer packages retrofitted, 1 new shared module, 1 new shared helper
module, 2 migrations, 1 new scheduled job, 4 `SignalSource` implementer call sites updated — no
UI, no new REST surface

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Spec-First Development | Spec exists at `specs/phases/111-claim-topology/spec.md`, status will move to `Implemented` in the same commit as the code per Definition of Done | PASS |
| II. Single-User Model | No `user_id`/tenancy touched anywhere in this feature; explicitly noted in spec Assumptions | PASS |
| III. Layered Package Architecture | New shared module lands in `core/ze-agents` (no domain knowledge — pure vocabulary/decay-math, same shape as existing `nli.py`); the closed `Provenance` enum is held to exactly the doctrine's four values, with plugin-owned inflow vocabulary (`email`, `calendar`) explicitly kept out per `specs/arch/plugin-domain-vocabulary.md` (this feature's own amendment to Principle III); no plugin imports `ze_core.*` or `ze_plugin.*` as a result of this feature; dependency direction unchanged (research.md §9 confirms zero new edges) | PASS |
| IV. Typed, Explicit Python | `ClaimKind`/`Provenance`/`DecayProfile` as `StrEnum`, `Confidence` as a dataclass in a `claims.py` (not `models.py`); `decay()` raises a typed `ZeError` subclass on missing profile params, never bare `ValueError` (contracts/claims.md §1) | PASS |
| V. Test Discipline | All four producer retrofits and the new decay job/staleness helper get unit tests with `AsyncMock`-mocked pools, no real DB, no real LLM; `make test-<pkg>` + `make lint` gate completion per package | PASS (enforced at task level) |
| VI. Explicit Persistence | Both new columns are hand-written raw-SQL Alembic migrations on their owning package's chain (`zcor`, `zm`); no ORM; `zcor` migration's `depends_on` already anchors to `zm006` per the existing chain | PASS |
| VII. One LLM Gateway, Local Embeddings | No LLM or embedding call added or changed by this feature | PASS (N/A) |

No violations. Complexity Tracking section below is not needed.

**Post-Phase-1 re-check**: research.md and data-model.md's design decisions (fetch-decay-write
in Python for `memory_facts`, moving two SQL-side cutoffs into Python via the shared helper)
were evaluated against the same seven gates above — neither introduces a new dependency edge,
a schema outside the owning package's chain, an ORM, a bare exception type, or an untested
path. Gate table holds unchanged post-design.

## Project Structure

### Documentation (this feature)

```text
specs/phases/111-claim-topology/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── claims.md        # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

This feature touches six existing packages in this monorepo — no new package is created.

```text
core/ze-agents/ze_agents/
└── claims.py                          # NEW — ClaimKind, Provenance, DecayProfile, Confidence, decay()

core/ze-agents/tests/
└── test_claims.py                     # NEW — unit tests for decay() per profile

core/ze-worldstate/ze_worldstate/
├── types.py                           # MODIFIED — LoopClaimKind aliases ClaimKind; LoopProvenance
│                                       #   becomes a plain string-constant namespace (not an Enum);
│                                       #   OpenLoop.provenance retypes to str
├── decay.py                           # MODIFIED — cascade_from_evidence calls shared decay()
└── extraction.py                      # MODIFIED — drops LoopProvenance(provenance) coercion;
                                        #   propose_loop_candidates uses the incoming str directly

core/ze-worldstate/tests/
└── (existing tests using LoopProvenance.CONVERSATION/.USER_DECLARED as fixtures — unchanged,
    per research.md §3's compatibility audit; new test asserting an unrecognized provenance
    string no longer raises)

core/ze-correlation/ze_correlation/
├── types.py                           # MODIFIED — Hypothesis.claim_kind, EvidenceRef.origin: Provenance
├── store.py                           # MODIFIED — PostgresHypothesisStore reads/writes claim_kind, new set_confidence()
├── engine.py                          # MODIFIED — Hypothesis(...) construction populates claim_kind
│                                       #   (added post-/speckit-analyze — see E1, E2)
├── jobs/
│   └── hypothesis_decay.py            # NEW — HypothesisDecayJob (@proactive_job)
└── migrations/versions/
    └── zcor00N_hypothesis_claim_kind.py  # NEW — additive, backfilled, non-nullable

core/ze-correlation/tests/
└── test_hypothesis_decay.py           # NEW

core/ze-memory/ze_memory/
├── types.py                           # MODIFIED — Signal.claim_kind, Signal.confidence
├── dream/promoter.py                  # MODIFIED — _run_confidence_decay calls shared decay() per
│                                       #   row; _promote's own INSERT populates claim_kind='inference'
│                                       #   (added post-/speckit-analyze — see E3)
├── consolidation_store.py             # MODIFIED — insert_merged_fact populates claim_kind='fact'
│                                       #   (added post-/speckit-analyze — see E3)
├── retriever.py                       # MODIFIED — fact-write INSERT populates claim_kind per
│                                       #   FR-010's rule; ingest_signal INSERT and get_signals_by_ids
│                                       #   read path populate/reconstruct claim_kind+confidence
│                                       #   (added post-/speckit-analyze — see E3, E4)
└── migrations/versions/
    ├── zm0NN_facts_claim_kind.py      # NEW — additive, backfilled, non-nullable
    └── zm0NN_signals_claim_kind.py    # NEW — memory_signals.claim_kind + .confidence, additive,
                                        #   backfilled, non-nullable (added post-/speckit-analyze — see E4)

core/ze-memory/tests/
└── (existing dream/promoter tests updated for the fetch-decay-write shape; new coverage for the
    three additional memory_facts write paths and the memory_signals round-trip)

core/ze-proactive/ze_proactive/
└── staleness.py                       # NEW — is_stale()

core/ze-proactive/tests/
└── test_staleness.py                  # NEW

core/ze-worldstate/ze_worldstate/jobs/
├── stale_suspicion.py                 # MODIFIED — calls is_stale() instead of inline cutoff
└── drift_sweep.py                     # MODIFIED — list_drift_candidates narrowed, filters via is_stale()

core/ze-worldstate/ze_worldstate/store.py  # MODIFIED — list_drift_candidates drops SQL-side cutoff predicate

core/ze-automation/ze_automation/
├── jobs/stuck_goals.py                # MODIFIED — calls is_stale() for the idle-days check
└── goals/postgres.py                  # MODIFIED — list_stuck narrowed, filters idle-days via is_stale()
                                        #   (alert_cooldown_days suppression stays SQL-side, unrelated to FR-015)

plugins/ze-calendar/, plugins/ze-finance/, plugins/ze-messenger/, plugins/ze-news/
└── (each SignalSource implementer's Signal(...) construction call site adds claim_kind, confidence)
```

**Structure Decision**: No new package. Every change lands inside an existing package's already-
established module layout (`types.py` for dataclasses, `jobs/` for `@proactive_job` classes,
`migrations/versions/` for the package's owned Alembic chain) — consistent with `CLAUDE.md`'s
"types.py everywhere" and "migrations live in the package that owns the Postgres store" rules.
`ze_agents/claims.py` is the one genuinely new module, placed beside `ze_agents/nli.py` as the
same kind of dependency-free shared contract (research.md §8).

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*
