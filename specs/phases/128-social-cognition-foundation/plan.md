# Implementation Plan: Social Cognition Foundation

**Branch**: `128-social-cognition-foundation` | **Date**: 2026-09-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/128-social-cognition-foundation/spec.md`

## Summary

Give Ze a `project` entity type and typed, decaying `WORKS_ON`
(person→project) / `COLLABORATES_WITH` (person↔person) edges in the
existing `core/cognition/ze-memory` graph — reusing the entity-extraction/upsert
pattern already established for `person` entities, not a new store or
pipeline. Retrofit `Relationship.confidence` from a plain `float` to the
shared `ze_agents.claims.Confidence` type with `DecayProfile.TIME_LINEAR`,
computed at read time from a new `last_contact` column (research.md §2).
Retire `plugins/ze-personal`'s dead, never-wired `PersonRelationship`/
`contact_relationships` schema outright (zero production callers, no seed
data). Route the existing `StaleFollowUpNudge` signal through
`core/arbitration/ze-priority`'s `PriorityView` as a fourth ranked source, via a new
structural `Protocol` (`RelationshipStalenessSource`) so the core package
never imports plugin code — the same shape as Phase 60's `SignalSource`.
Explicitly out of scope: project-person co-occurrence inference
(`specs/arch/social-cognition.md`'s rollout step 3, a later phase).

## Technical Context

**Language/Version**: Python 3.12 (backend); no new frontend surface (spec Assumption — `/brain/graph` already generalizes to any `entity_type`)

**Primary Dependencies**: `ze_agents.claims` (`Confidence`, `DecayProfile`, `decay()`), `core/cognition/ze-memory`'s `GraphStore`/extractor, `core/arbitration/ze-priority`'s `PriorityView`/`scoring.py`, `plugins/ze-personal`'s `PersonStore`/`ContactsConsolidator`/extractors, LangGraph result hooks (`memory_hooks.py`)

**Storage**: PostgreSQL — `core/cognition/ze-memory`'s `zm` chain (migration `zm019`: add `memory_relationships.last_contact`), `plugins/ze-personal`'s `zc` chain (migration `zc029`: drop `contact_relationships`)

**Testing**: pytest, `asyncio_mode=auto`; mock `asyncpg` pools with `AsyncMock`, no real DB, no real LLM (mock `client.complete`); a dedicated elapsed-time decay test per SC-004 (constructs a `Relationship`/calls the hydration path with a synthetic `last_contact` in the past — no real clock manipulation)

**Target Platform**: Linux server (`apps/ze-api`), single-user

**Project Type**: Backend monorepo feature — no new REST endpoint, no new UI (spec Assumption; `PriorityView`'s existing `/api/v0/priority/snapshot` surfaces the new source automatically once wired)

**Performance Goals**: N/A — no new hot path; extraction and decay computation are O(1) additions to existing per-message/per-read work

**Constraints**: Must not introduce a core (`ze-priority`) → plugin (`ze-personal`) import (Constitution III) — resolved via the `RelationshipStalenessSource` protocol (research.md §3); must not add a scheduled decay job (FR-006 — no new relationship-specific mechanism) — resolved via read-time decay computation (research.md §2)

**Scale/Scope**: Single user, existing memory-graph and priority-view scale; no new indices beyond what `last_contact`-based queries need if any are added during tasks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Check | Result |
|---|---|---|
| I. Spec-First Development | Spec exists at `specs/phases/128-social-cognition-foundation/spec.md`, status will be updated to Done in the same commit as implementation (per Definition of Done) | ✅ Pass |
| II. Single-User Model | No `user_id`/multi-tenancy introduced — `project`/relationship edges are global entities in the single-user graph, same as `person` today | ✅ Pass |
| III. Layered Package Architecture | **Initial risk**: routing a `ze-personal` (plugin) signal through `ze-priority` (core) via a direct dependency would invert the mandated dependency direction. **Resolved** in research.md §3 / contracts/priority-relationship-source.md: `ze-priority` defines a structural `Protocol` it depends on; `PersonStore` satisfies it with zero plugin-side changes; wiring happens only at `apps/ze-api`'s composition root. No core package gains a plugin import. | ✅ Pass (after design) |
| III. (entity_type as core enum) | `entity_type`/predicates remain documented string conventions, not new core-owned closed enums — matches existing precedent, no violation of "closed enum only when doctrine mandates an exact closed set" | ✅ Pass |
| IV. Typed, Explicit Python | `Relationship.confidence` moves from bare `float` to the shared `Confidence` dataclass (typed); no Pydantic introduced outside `ze_api/api/schemas.py` (no new REST surface, so N/A) | ✅ Pass |
| V. Test Discipline | New tests planned for: `zm019`/`zc029` migrations, `entity_type="project"` extraction, `WORKS_ON`/`COLLABORATES_WITH` upsert + reinforcement, `Relationship.confidence` read-time decay (SC-004's dedicated test), `PriorityView`'s fourth source (present, absent, and failing), `briefing.py`'s new call site, deletion of `PersonRelationship`/`contact_relationships` tests | ✅ Pass (planned, enforced at `/speckit-tasks`/`/speckit-implement`) |
| VI. Explicit Persistence | Both migrations are hand-written raw-SQL Alembic, owned by the package that owns the table (`zm019` in ze-memory, `zc029` in ze-personal), correct chain/prefix per `CLAUDE.md`'s ownership table | ✅ Pass |
| VII. One LLM Gateway, Local Embeddings | Extraction extension reuses the existing extractor/consolidator's `LLMClient`/embedding singleton — no new provider, no new embedding model | ✅ Pass |

No violations requiring Complexity Tracking justification.

## Project Structure

### Documentation (this feature)

```text
specs/phases/128-social-cognition-foundation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── memory-graph-vocabulary.md
│   └── priority-relationship-source.md
└── tasks.md              # Phase 2 output (/speckit-tasks — not yet generated)
```

### Source Code (repository root)

```text
core/cognition/ze-memory/ze_memory/
├── types.py                          # entity_type comment: + "project"
├── extractor.py                      # extraction prompt: + "project" recognized type
└── graph/
    ├── predicates.py                 # + WORKS_ON, COLLABORATES_WITH in ALL_PREDICATES
    ├── types.py                      # Relationship.confidence: float → Confidence; + last_contact
    ├── store.py                      # GraphStore: read-time decay hydration; ON CONFLICT + last_contact
    └── migrations/versions/
        └── zm019_relationship_last_contact.py   # new

core/arbitration/ze-priority/ze_priority/
├── types.py                          # SourceKind + "relationship"; + RelationshipSignal; + RelationshipStalenessSource Protocol
├── scoring.py                        # + score_relationship_staleness()
└── view.py                           # PriorityView: + optional relationship_source param; 4th try/except in rank()

plugins/ze-personal/ze_personal/
├── contacts/
│   ├── types.py                      # remove PersonRelationship
│   ├── store.py                      # remove add_relationship/get_relationships
│   ├── consolidator.py               # _extract_candidates(): + project/relationship-edge output
│   └── extractors.py                 # extract_email_contacts/extract_calendar_contacts: + project/collaboration mentions
├── graph/memory_hooks.py             # + project/relationship-edge write path alongside contact_proposal_hook
├── jobs/briefing.py                  # + priority_view dependency; replace list_stale_for_follow_up call site
├── plugin.py                         # remove contact_relationships domain registration
└── migrations/versions/
    └── zc029_drop_contact_relationships.py       # new

core/ops/ze-onboarding/ze_onboarding/
└── reset.py                          # remove contact_relationships truncation entry

apps/ze-api/ze_api/
└── container.py                      # wire PersonStore into PriorityView's relationship_source arg
```

**Structure Decision**: This is a backend-only, multi-package feature inside
the existing monorepo layout (`core/`, `plugins/`, `apps/` — see `CLAUDE.md`'s
repository layout). No new package is created; every file touched already
exists except the two migrations. No frontend changes (spec Assumption).

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*
