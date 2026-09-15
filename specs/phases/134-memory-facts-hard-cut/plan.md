# Implementation Plan: Memory Facts Hard-Cut onto Shared Claim Vocabulary

**Branch**: `134-memory-facts-hard-cut` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/134-memory-facts-hard-cut/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Hard-cut `Fact` and `memory_facts` onto `ze_agents.claims` (`ClaimKind`, `Provenance`, shared
`TIME_LINEAR` confidence decay). Drop the `"raw"` / `"synthesized"` string dialect. Persist
doctrine provenance on every insert (today the hot write path omits the column and relies on
`DEFAULT 'raw'`). Remove `propose_facts` from public `MemoryStore`. Persist only via the
Phase 133 contribution `write=` callback bound to a private store method. One `zm` migration;
no dual-write. Depends on [133-perception-facts-seam](../133-perception-facts-seam/spec.md);
does not re-migrate those call sites.

## Technical Context

**Language/Version**: Python 3.12 (asyncio-native, matches monorepo)

**Primary Dependencies**: `ze-agents` (`ClaimKind`, `Provenance`, `decay`, `DecayProfile`),
`ze-memory` (`Fact`, `PostgresMemoryStore`, `MemoryStore` Protocol), `ze-plugin` /
`ze-collision` (133's `write=` already wraps persist), `ze-logging`

**Storage**: PostgreSQL `memory_facts.provenance` (existing TEXT column) — rewrite values,
drop `'raw'` default, NOT NULL + CHECK to doctrine set. No new table.

**Testing**: pytest, `asyncio_mode = "auto"`; mock asyncpg / no real LLM. Package targets:
`make test-memory`, plus `make test-api` for fact-quality route, `make test-core` /
ingestion / messenger / onboarding / automation only for compile breaks from `Fact` type
change — not for re-doing 133 call-site tests.

**Target Platform**: Backend (`apps/ze-api` + `core/cognition/ze-memory`)

**Project Type**: Hard-cut inside existing monorepo packages (not a new app)

**Performance Goals**: No new hot-path LLM; retrieval SQL stays the same shape minus
`COALESCE(..., 'raw')`

**Constraints**: Principle VIII — no shim, no dual-write, no public `propose_facts` alias.
If 133 left a production caller, stop (FR-007). Agent-context updater script is absent in
this repo; skip.

**Scale/Scope**: Single-user; one table; ~10 SQL call sites that mention fact provenance;
Protocol + dataclass + quality REST + memory-feed projection

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 134 exists; governed by contribution-seam step 6, claim-topology leftover, pre-v1 hard-cuts | PASS |
| II. Single-User | No `user_id`; fact rows stay global | PASS |
| III. Layered Package Architecture | Types in `ze_memory`; shared enums stay in `ze_agents.claims`; no new Provenance members (plugin-domain-vocabulary); plugins keep importing `ze_sdk.memory` | PASS |
| IV. Typed, Explicit Python | `Fact.provenance: Provenance`, `Fact.claim_kind: ClaimKind`; dataclass in `types.py`; reject unknown provenance with typed `ZeError` on insert, not `ValueError` | PASS |
| V. Test Discipline | Unit tests mock pools; update fixtures from `"raw"`; no real DB/LLM | PASS |
| VI. Explicit Persistence | `zm020` on ze-memory chain, `down_revision = zm019`; raw SQL | PASS |
| VII. One LLM Gateway | No new LLM/embedding path | PASS |
| VIII. Pre-v1 Hard Cuts | Schema + Protocol break in this phase; no wrap of `propose_facts` | PASS |

No violations. Complexity Tracking empty.

**Post-design re-check**: Design keeps Provenance closed at four values; private persist is
not a renamed public API; REST `by_provenance` keys break (allowed). PASS.

## Project Structure

### Documentation (this feature)

```text
specs/phases/134-memory-facts-hard-cut/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── memory-store.md
│   ├── memory-facts-schema.md
│   └── fact-quality-api.md
└── tasks.md
```

### Source Code (repository root)

```text
core/cognition/ze-memory/ze_memory/
├── types.py                 # Fact.provenance / claim_kind
├── store.py                 # MemoryStore Protocol — drop propose_facts
├── retriever.py             # private persist; INSERT provenance
├── projection.py            # _fact_from_row
├── policies.py              # COALESCE removal
├── entity_anchor.py
├── retrieval_rerank.py
├── consolidation_store.py   # INSERT provenance
├── admin.py                 # feed SQL
├── dream/promoter.py        # decay WHERE synthesized (enum value unchanged)
└── migrations/versions/zm020_facts_doctrine_provenance.py

apps/ze-api/ze_api/api/routes/memory.py   # get_fact_quality buckets
apps/ze-api/ze_api/api/schemas.py         # MemoryFactQualityResponse keys

packages/ze-sdk/ze_sdk/memory.py          # re-exports Protocol (no extra API)

core/cognition/ze-memory/tests/
apps/ze-api/tests/api/                    # fact quality
```

**Structure Decision**: Stay inside `ze-memory` + the one REST diagnostic that counts `raw`.
133 already owns call sites (`write_memory`, `MemorySink`, inbound, onboarding, goal
promotion). This phase only retargets their `write=` callback from `propose_facts` to the
private persist method if those files still name `propose_facts` as the callback — a
mechanical rename, not a new routing design.

## Complexity Tracking

> None
