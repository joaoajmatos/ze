# Implementation Plan: Claim Honesty Fixes

**Branch**: `199-claim-honesty-fixes` | **Date**: 2026-10-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/199-claim-honesty-fixes/spec.md`

## Summary

This phase fixes four wrong claim labels, as four accepted ADRs decide.

- **B7**: perception stamps the facts it reads from the user, or from the user's own sources, `prompt_supplied`. Dream decay and expiry also require `dream_run_id IS NOT NULL`. The promoter stops inserting a column `memory_facts` lacks. `zm026` re-stamps existing perception facts and reports the decay-damaged count. Contact provenance is derived from the source type, and `zc041` re-stamps contacts.
- **B12**: a loop's claim kind becomes a property derived from its state. `zw006` drops `open_loops.claim_kind`, and the loops REST field becomes nullable.
- **B8**: Executive is licensed for priority and suspicion only.
- **B3**: a new `LoopStore.resolve` closes a suspected, active or drifting loop and links the resolving evidence in one transaction. The generic transition table is unchanged.

Every fix starts with a failing test through the real interface. The SQL fixes are tested on test-pg. Research: [research.md](research.md). Data: [data-model.md](data-model.md). Contracts: [contracts/](contracts/). Verification: [quickstart.md](quickstart.md).

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript (ze-web readers, generated client)

**Primary Dependencies**: asyncpg, Alembic (raw SQL), FastAPI/Pydantic (REST schema only), `@hey-api/openapi-ts` via `make codegen`

**Storage**: PostgreSQL. Tables touched: `memory_facts` (`zm`), `open_loops` (`zw`), `contacts` and `contact_sources` (`zc`, ze-personal). `memory_relationships` gets resolve evidence rows; its schema does not change.

**Testing**: pytest (`asyncio_mode=auto`), test-pg (`make test-pg`, `@pytest.mark.pg`, `apps/ze-api/tests/pg/`), vitest and `tsc` for the web readers

**Target Platform**: Ze running locally (self-hosted)

**Project Type**: monorepo (core packages, plugins, ze-api, ze-web)

**Performance Goals**: none new. The re-stamps are single `UPDATE`s over at most a few thousand rows.

**Constraints**: pre-v1 hard cuts (no dual read of the dropped column, no compatibility argument on `OpenLoop`). Plugins import only from `ze_sdk.*` and `ze_personal.*`. Floor 198 runs in parallel (research R9).

**Scale/Scope**: about 20 source files, 3 migrations, about 30 test files (mostly one-line constructor edits), 3 web files and the generated client.

## Constitution Check

*GATE: passed before Phase 0 and re-checked after Phase 1.*

- **I. Spec-First Development**: PASS. The spec, clarifications and four ADRs exist. The status moves to Implemented in the commit that finishes the phase.
- **II. Single-User Model**: PASS. No user scoping.
- **III. Layered Package Architecture**: PASS. Each change stays in its owning package: ze-plugin (licence), ze-memory (dream, zm026), ze-core (one provenance line), ze-ingestion, ze-messenger (through `ze_sdk`), ze-worldstate, ze-personal, ze-prospecting (imports `ze_personal`, an allowed edge), ze-api (REST schema) and ze-web. There are no new import edges. `Provenance` keeps its four doctrine values.
- **IV. Typed, Explicit Python**: PASS. `ContactSourceTypeError(ZeCoreError)` is a typed error. Derived values are properties on dataclasses. There is no Pydantic outside `ze_api/api/`.
- **V. Test Discipline**: PASS. Each story starts with a failing test, SQL is tested on test-pg, and `make test-<pkg>` plus `make lint` gate each lane.
- **VI. Explicit Persistence**: PASS. The migrations are hand-written raw SQL on their owning chains (`zm026`, `zw006`, `zc041`).
- **VII. One LLM Gateway, Local Embeddings**: PASS. No LLM change.
- **VIII. Pre-v1 Hard Cuts**: PASS. The column is dropped, not left unread. The `OpenLoop(claim_kind=...)` and `ContactProposal.provenance` arguments are deleted, not ignored. The re-stamps rewrite the wrong labels instead of keeping two meanings.

## Project Structure

### Documentation (this feature)

```text
specs/phases/199-claim-honesty-fixes/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── loop-store.md
│   ├── rest-loops.md
│   └── migrations.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
core/contracts/ze-plugin/ze_plugin/contribution.py                # B8 licence
core/cognition/ze-memory/ze_memory/dream/promoter.py              # B7 decay/expiry marker, insert fix
core/cognition/ze-memory/ze_memory/migrations/versions/zm026_perception_fact_provenance.py
core/engine/ze-core/ze_core/orchestration/nodes/memory.py         # B7, line ~217 only
core/ops/ze-ingestion/ze_ingestion/sink.py                        # B7
plugins/ze-messenger/ze_messenger/inbound/processor.py            # B7
core/ops/ze-seed/ze_seed/narrative/persona.yaml                   # seed facts → prompt_supplied
core/cognition/ze-worldstate/ze_worldstate/{types,store,extraction,tracking,rest}.py   # B12, B3
core/cognition/ze-worldstate/ze_worldstate/migrations/versions/zw006_drop_loop_claim_kind.py
apps/ze-api/ze_api/api/v0/loops/schemas.py                        # nullable claim_kind
plugins/ze-personal/ze_personal/contacts/{types,errors,consolidator,extractors,store}.py
plugins/ze-personal/ze_personal/graph/memory_hooks.py
plugins/ze-personal/ze_personal/jobs/social_cooccurrence.py
plugins/ze-personal/ze_personal/migrations/versions/zc041_contact_source_provenance.py
plugins/ze-prospecting/ze_prospecting/agents/tools.py
packages/ze-client/src/generated/                                 # make codegen
apps/ze-web/src/pages/world/lib/concerns.ts
apps/ze-web/src/widgets/loops-rail/ui/LoopsRail.tsx
apps/ze-web/src/pages/doing-goal/ui/DoingGoalPage.tsx
apps/ze-api/tests/pg/test_{dream_decay,zm026,loop_claim_kind,loop_resolve,contact_provenance}_pg.py
```

**Structure Decision**: Each change lives in the package that owns the table or the behaviour (research R2–R7). There is no new module apart from the contacts errors file. The resolve event is one store method, which phase 203 later moves into its lifecycle module.

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first, T001): record the three migration revisions and file names (`zm026`, `zw006`, `zc041`) in the floor's Handoffs note, and confirm with floor 198 that it still adds none. There are no shared types to stub, because the lanes touch disjoint packages. The one cross-lane edge is the nullable REST field. The `loops` lane changes `schemas.py`, and `lead` then regenerates the client and fixes the web readers (T036–T037).

| Lane | Model / role | Owns (files and dirs, disjoint) | Tasks | Starts after | Reviewer |
|------|--------------|---------------------------------|-------|--------------|----------|
| lead | Sonnet ENG lead | `packages/ze-client/src/generated/`, `apps/ze-web/src/pages/world/lib/concerns.ts`, `apps/ze-web/src/widgets/loops-rail/ui/LoopsRail.tsx`, `apps/ze-web/src/pages/doing-goal/ui/DoingGoalPage.tsx` and their colocated tests; merges; final gates | T001, T035–T040 | - | floor reviewer (Maestro assigns) |
| facts | Sonnet ENG | `core/engine/ze-core/ze_core/orchestration/nodes/memory.py` (the provenance hunk at ~217 only), `core/engine/ze-core/tests/orchestration/nodes/test_memory.py`, `core/ops/ze-ingestion/ze_ingestion/sink.py`, `core/ops/ze-ingestion/tests/test_sink.py`, `plugins/ze-messenger/ze_messenger/inbound/processor.py`, `plugins/ze-messenger/tests/test_inbound_processor.py`, `core/cognition/ze-memory/ze_memory/dream/promoter.py`, `core/cognition/ze-memory/tests/dream/test_promoter.py`, `core/cognition/ze-memory/ze_memory/migrations/versions/zm026_perception_fact_provenance.py`, `core/ops/ze-seed/ze_seed/narrative/persona.yaml`, `core/ops/ze-seed/tests/test_loader.py`, `apps/ze-api/tests/pg/test_dream_decay_pg.py`, `apps/ze-api/tests/pg/test_zm026_pg.py`, `core/cognition/ze-memory/ze_memory/consolidation_store.py`, `core/cognition/ze-memory/ze_memory/consolidator.py`, `core/cognition/ze-memory/tests/test_consolidator.py`, `core/cognition/ze-memory/tests/test_consolidator_nli.py`, `apps/ze-api/tests/pg/test_consolidation_merge_pg.py` | T002–T013, T044–T045 | contract step | floor reviewer (Maestro assigns) |
| loops | Sonnet ENG | `core/cognition/ze-worldstate/ze_worldstate/{types,store,extraction,tracking,rest}.py`, `core/cognition/ze-worldstate/ze_worldstate/migrations/versions/zw006_drop_loop_claim_kind.py`, `core/cognition/ze-worldstate/tests/` (all files), `core/arbitration/ze-priority/tests/factories.py`, `core/arbitration/ze-priority/tests/test_turn.py`, `core/arbitration/ze-priority/tests/compose/test_rules_topic.py`, `core/arbitration/ze-priority/tests/compose/test_rules_slipping.py`, `core/arbitration/ze-priority/tests/compose/test_rules_decisions.py` (delete `claim_kind=` lines only), `apps/ze-api/ze_api/api/v0/loops/schemas.py`, `apps/ze-api/tests/api/test_loops_route.py`, `apps/ze-api/tests/pg/_builders.py`, `apps/ze-api/tests/pg/test_loop_claim_kind_pg.py`, `apps/ze-api/tests/pg/test_loop_resolve_pg.py` | T014–T026 | contract step | floor reviewer (Maestro assigns) |
| contacts | Sonnet ENG | `plugins/ze-personal/ze_personal/contacts/{types,errors,consolidator,extractors,store}.py`, `plugins/ze-personal/ze_personal/graph/memory_hooks.py`, `plugins/ze-personal/ze_personal/jobs/social_cooccurrence.py`, `plugins/ze-personal/ze_personal/migrations/versions/zc041_contact_source_provenance.py`, `plugins/ze-personal/tests/contacts/`, `plugins/ze-personal/tests/graph/test_memory_hooks.py`, `plugins/ze-personal/tests/jobs/test_social_cooccurrence.py`, `plugins/ze-prospecting/ze_prospecting/agents/tools.py`, `plugins/ze-prospecting/tests/agents/test_tools.py`, `apps/ze-api/tests/pg/test_contact_provenance_pg.py` | T029–T034 | contract step | floor reviewer (Maestro assigns) |
| jr1 | Haiku JR | `core/contracts/ze-plugin/ze_plugin/contribution.py` (the `_LICENSE` Executive entry only), `core/contracts/ze-plugin/tests/test_contribution.py` | T027–T028 | contract step | floor reviewer (Maestro assigns) |
| docs | Haiku DOCS | `docs/dreaming.md`, `docs/architecture.md`, `docs/memory.md`, `docs/goals.md`, `docs/features.md`, `core/cognition/ze-worldstate/README.md`, `core/cognition/ze-memory/README.md`, `plugins/ze-personal/README.md`, `AGENTS.md`, `specs/README.md` (199 Status cell only), `specs/phases/199-claim-honesty-fixes/spec.md` (Status line only), `specs/arch/contribution-seam.md` (check only) | T041–T043 | all lanes merged | floor reviewer (Maestro assigns) |

**Rules**:

- **One lane per file.**
- **`nodes/memory.py` is shared with floor 198.** The `facts` lane edits only the `PerceptionFactSubmit(... provenance=...)` hunk (around line 217). Floor 198's engine lane owns lines 252-342. Keep the hunks apart.
- **Branches.** Each lane works on a sub-branch of the floor branch. `lead` merges `jr1` → `facts` → `contacts` → `loops`, then runs T036–T040. Each lane is reviewed as it finishes.
- **`jr1` is Haiku** because its two tasks carry the exact change and the exact failing test.
- **`docs` runs last**, from the finished diff.
- **Cross-floor (research R9).** The `loops` lane deletes only `claim_kind=` lines in the four ze-priority test files and in `ze-worldstate/tests/test_surfacing.py`; floor 198's attention lane owns those files on its own floor. Whichever floor lands second re-runs `make codegen` instead of hand-merging generated files.

## Complexity Tracking

None.
