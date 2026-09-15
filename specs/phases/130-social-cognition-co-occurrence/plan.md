# Implementation Plan: Social Cognition Co-Occurrence

**Branch**: `130-social-cognition-co-occurrence` | **Date**: 2026-09-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/130-social-cognition-co-occurrence/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Phase 128 gave the memory graph `project` entities and `WORKS_ON`/`COLLABORATES_WITH`
edges, but only writes them when an LLM extraction step already named the link
outright (`ze_personal/contacts/consolidator.py` → `ze_personal/graph/memory_hooks.py`,
a direct, full-confidence write with no corroboration gate). This phase adds the
first *inferred* path: a new proactive job scans recent (30-day) communication
evidence for person↔project and person↔person co-occurrence that was never
named as a fact, scores it with contacts' existing `SOURCE_WEIGHTS`, and holds it
as a persisted `ze_correlation.Hypothesis` (`ClaimKind.INFERENCE`, `SourceFunction.
REFLECTION` — the same license the correlation engine's own hypotheses already
use). Only once corroborated by repeated independent evidence, or the user
explicitly confirms, does the job promote the pair to a real `WORKS_ON`/
`COLLABORATES_WITH` identity edge — reusing Phase 128's entity-upsert logic but,
unlike Phase 128's direct path, routing the write through the contribution seam
(`SourceFunction.SOCIAL_COGNITION`, licensed for `ClaimKind.IDENTITY` only —
verified against `core/contracts/ze-plugin/ze_plugin/contribution.py`'s
`_LICENSE` table, which is exactly why hypothesis formation and promotion must
use two different `SourceFunction`s, not one).

No new correlation package, no new store, no new REST surface, no relationship-
strength score, no project lifecycle. `ze-correlation`'s existing `Hypothesis`/
`PostgresHypothesisStore`/seam-submission shape is reused as-is, gaining two
narrow additions (a `confirmed` flag and a `promoted_at` marker) and a thin
`ze_sdk.correlation` re-export so `ze-personal` — which owns `SOURCE_WEIGHTS`
and the person/project domain — can reach it without a forbidden `ze_core`/
direct-core-package import. Conversational surfacing stays hedged by construction:
a new `who_is_on_project` tool reads confirmed graph edges and any matching
unconfirmed hypotheses separately and never blends the two.

## Technical Context

**Language/Version**: Python 3.11 (`core/cognition/ze-correlation`,
`packages/ze-sdk`, `plugins/ze-personal`, `apps/ze-api` wiring only)

**Primary Dependencies**: Existing `ze_correlation` (`Hypothesis`, `EvidenceRef`,
`PostgresHypothesisStore`), existing `ze_collision.submit_and_detect_collisions`
/ `ze_plugin.contribution.Contribution`, existing `ze_memory.graph` (`GraphStore`,
`Relationship`, `WORKS_ON`/`COLLABORATES_WITH` predicates), existing
`ze_proactive.proactive_job` decorator, `asyncpg`. No new third-party dependency.

**Storage**: Postgres `correlation_hypothesis` (existing table, two new nullable
columns via a new migration on the existing `zcor` chain) — no new table, no new
per-social-cognition store. `memory_relationships` (existing, Phase 128 shape)
receives writes only after promotion, same shape as Phase 128's direct path.

**Testing**: `pytest` via `make test-ze-correlation` (store column + query
additions), `make test-ze-personal` (new job, new tools, promotion path), and
`make test-ze-sdk` if the new `ze_sdk.correlation` module needs its own smoke
test. `asyncio_mode = "auto"`, no real DB/LLM per Constitution V — the job's
evidence-weighting and corroboration-gate logic is pure/deterministic and unit-
testable without mocking an LLM at all (FR-004 explicitly forbids inventing an
LLM-scored CC-discount).

**Target Platform**: Existing `ze-api` backend process (proactive job runs on
the existing scheduler; no new deployment unit, no `ze-web` change — FR-011).

**Project Type**: Backend only. No frontend work — existing `/brain/graph` view
and conversational ask are the only read surfaces (FR-011).

**Performance Goals**: SC-001 (hedged answer with ≥1 cited evidence item, no
identity edge, 100% in the reply-and-meeting fixture); SC-002 (promoted edge
readable from either endpoint post-corroboration/confirm, control CC-only pair
never promoted); SC-003 (0 identity edges from a single CC-only broadcast
fixture); SC-004 (aged-out membership omitted from "currently on this project"
100% of the time in the aged fixture); SC-005 (unconfirmed hypothesis never
consumes the shared daily interruption budget, tested alongside a real drifting
loop on the same day).

**Constraints**: 30-day recency window reuses `ze_proactive.staleness.is_stale()`
verbatim, no new decay constant (FR-003). Evidence weighting reuses
`SOURCE_WEIGHTS` verbatim from `ze_personal.contacts.types`, no new CC-discount
formula (FR-004). Corroboration threshold is a plan-time default (this document,
Decision 3 in `research.md`), not spec-pinned. No `active`/`closed` project
lifecycle (FR-007). No relationship-strength score / cadence field / per-thread
membership (FR-008, deferred ADR step 4). No predicate beyond `COLLABORATES_WITH`
(FR-009). Unconfirmed inferences MUST NOT enter `list_stale_for_follow_up`
(FR-010) or any other shared-budget source.

**Scale/Scope**: Single user, bounded number of known person/project entities —
same order of magnitude as Phase 128's consolidator, no new scale concern.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First Development**: Governed by spec 130 under
  `specs/arch/social-cognition.md` rollout step 3. Status flips to `Planned` in
  this commit, `Implemented` at the end of `/speckit-implement`. PASS.
- **II. Single-User Model**: No `user_id`, no per-user scoping anywhere in the
  new job, store columns, or tools — same single-user graph Phase 128 already
  established. PASS.
- **III. Layered Package Architecture**: The co-occurrence scoring algorithm
  and `SOURCE_WEIGHTS` stay in `ze-personal` (the domain owner), never move
  into `ze-correlation` (which stays domain-agnostic — it gains no knowledge of
  "person"/"project"). `ze-personal` reaches `ze_correlation`'s `Hypothesis`/
  store types through a new `ze_sdk.correlation` re-export module — mirroring
  the existing `ze_sdk.memory`/`ze_sdk.automation` pattern exactly, not a
  `ze_core`/`ze_plugin` direct import (both remain forbidden). This is a
  planned widening of the SDK surface, not an exception: `ze-sdk` gains
  `ze-correlation` as a dependency the same way it already depends on
  `ze-memory`/`ze-automation`. Promotion writes go through the existing
  contribution seam (`ze_sdk.contribution.submit_and_detect_collisions`), same
  as every other identity write. PASS — no Complexity Tracking entry needed.
- **IV. Typed, Explicit Python**: New fields (`confirmed`, `promoted_at`) as
  plain columns on the existing `Hypothesis` dataclass; job/tool inputs and
  outputs are dataclasses in `ze_personal/social/types.py`. No new error
  subclass needed — `UnlicensedClaimKindError`/`ContributionError` (existing,
  `ze_plugin.contribution`) already cover a misrouted `SourceFunction`. PASS.
- **V. Test Discipline**: New job tests construct `Hypothesis`/`EvidenceRef`
  fixtures directly (no LLM call in the co-occurrence path at all — it is pure
  scoring over already-extracted evidence); `AsyncMock` for `HypothesisStore`/
  `GraphStore`/`PushLog`/`CollisionLogStore`. PASS.
- **VI. Explicit Persistence**: One new hand-written Alembic migration
  (`zcor003`) on the existing `ze-correlation` (`zcor`) chain, raw SQL, two
  nullable columns. No ORM, no new table. PASS.
- **VII. One LLM Gateway, Local Embeddings**: Untouched — corroboration and
  evidence-weighting are deterministic (FR-004), no new LLM or embedding call
  introduced by this phase. PASS.

No violations. Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/phases/130-social-cognition-co-occurrence/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── social-cooccurrence-contract.md  # Seam contributions, SDK surface, tool signatures
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
core/cognition/ze-correlation/ze_correlation/
├── store.py                     # PostgresHypothesisStore gains confirm(id),
│                                 # mark_promoted(id), list_by_entities(entity_ids)
└── migrations/versions/
    └── zcor003_hypothesis_confirmation.py  # ADD COLUMN confirmed BOOLEAN
                                              # NOT NULL DEFAULT false,
                                              # promoted_at TIMESTAMPTZ NULL

packages/ze-sdk/
├── pyproject.toml               # + "ze-correlation" dependency
└── ze_sdk/
    └── correlation.py           # NEW — re-exports Hypothesis, EvidenceRef,
                                  # HypothesisStore protocol / PostgresHypothesisStore,
                                  # mirroring ze_sdk/memory.py's shape

plugins/ze-personal/ze_personal/
├── social/                      # NEW subpackage
│   ├── __init__.py
│   ├── types.py                 # CoOccurrenceCandidate, CorroborationResult
│   ├── scoring.py                # SOURCE_WEIGHTS-based evidence scoring +
│   │                              # corroboration gate (mirrors DreamPromoter's
│   │                              # support_count/distinct_days shape)
│   └── tools.py                  # @tool who_is_on_project,
│                                  # @tool confirm_project_membership
├── jobs/
│   └── social_cooccurrence.py    # NEW — SocialCooccurrenceJob(@proactive_job):
│                                  # scan → score → form/update Hypothesis via
│                                  # seam (REFLECTION/INFERENCE) → corroboration
│                                  # check → promote via seam
│                                  # (SOCIAL_COGNITION/IDENTITY)
├── graph/memory_hooks.py         # + _write_relationship_edge_via_seam(),
│                                  # reusing the existing entity-upsert logic
│                                  # but wrapping the graph write in
│                                  # submit_and_detect_collisions (Phase 128's
│                                  # direct path is untouched — still unseamed,
│                                  # out of scope to retrofit here)
├── plugin.py                     # agent_module_paths() + "ze_personal.social.tools";
│                                  # jobs() + self.social_cooccurrence
└── tests/social/                 # NEW — scoring, corroboration gate, job,
                                   # tools, promotion-via-seam

apps/ze-api/ze_api/
└── container.py                  # wire SocialCooccurrenceJob's dependencies
                                   # (hypothesis_store via ze_sdk.correlation,
                                   # graph_store, collision_store, nli_client,
                                   # push_log) — same DI shape as existing jobs
```

**Structure Decision**: No new packages, no new datastore, no new REST route.
One new subpackage (`ze_personal/social/`) inside the existing plugin that
already owns `SOURCE_WEIGHTS` and the person/project domain; one new re-export
module (`ze_sdk/correlation.py`) so that subpackage can reach `ze-correlation`'s
existing types without a layering violation; one new migration on
`ze-correlation`'s existing chain. `ze-web` is untouched.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

*No violations — table intentionally omitted.*
