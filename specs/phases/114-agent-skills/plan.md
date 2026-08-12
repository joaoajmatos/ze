# Implementation Plan: Agent Skills

**Branch**: `114-agent-skills` | **Date**: 2026-08-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/phases/114-agent-skills/spec.md`

## Summary

Add a standard-compatible Agent Skills system to Ze: users import `SKILL.md` (optionally
bundled with reference files in an archive) from a URL, review the full parsed content, and
approve it before it can ever influence a conversation. Approved skills are matched to a turn
two ways — automatic embedding-similarity against the message (reusing the `EmbeddingRouter`
pattern) and explicit `/skill-name` invocation — applied identically across every agent (no
per-agent scoping), never granting new tools (only narrowing an agent's existing `tools` list),
and always surfaced on the turn via `MessageTrace`/`trace_update`. A new core package
`ze-skills` (wired directly into `apps/ze-api`, like `ze-worldstate`/`ze-automation` — not a
`ZePlugin`) owns the domain model, parsing/import, matching, and a daily proactive recheck job
that reverts a skill to pending review if its source content changed. Developer-authored skills
ship bundled inside plugin packages via a new `ZePlugin.bundled_skill_paths()` hook, mirroring
the existing `agent_module_paths()` pattern.

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript/React (ze-web) — matches existing stack.

**Primary Dependencies**: `ze-agents`, `ze-proactive`, `ze-logging`, `ze-data` (new `ze-skills`
core package deps, mirroring `ze-worldstate`'s dependency shape); `httpx` (URL fetch, already a
workspace dependency e.g. in `ze-ingestion`); `PyYAML` (frontmatter parsing — already a
transitive dependency via existing config loading; no new top-level dependency expected);
Python stdlib `zipfile` (archive extraction, no new dependency). Reuses `ze_core`'s
`EmbeddingRouter`/embedder singleton via dependency injection (no new package coupling from
`ze_core` — matches how `surface_loops` consumes `loop_surfacer` via `config["configurable"]`).

**Storage**: PostgreSQL via asyncpg, own migration chain (prefix `zsk`), tables `skills`,
`skill_reference_files`, `skill_reviews` — see [data-model.md](data-model.md). No new table for
"Skill Usage" (spec's third Key Entity): usage is captured as a new `skills_used` field on the
existing `MessageTrace` dataclass, persisted in the existing `messages.trace` JSONB column
(phase 89), avoiding a redundant table for data already covered by the trace mechanism.

**Testing**: pytest (`ze-skills/tests/`, `asyncio_mode = "auto"`, mock asyncpg pools and
`httpx` responses, no real network/DB in unit tests — per `CLAUDE.md` Testing conventions);
vitest for the ze-web management page.

**Target Platform**: Same as the rest of Ze — deployed FastAPI service + React SPA; no change
to deployment architecture (per spec Assumptions).

**Project Type**: Web application (existing backend + frontend monorepo structure).

**Performance Goals**: Skill matching must not add perceptible latency to a turn — embedding
comparison only (no extra LLM call), same order of cost as `EmbeddingRouter`'s existing
per-turn agent-routing embedding.

**Constraints**: No new tool-calling capability may be granted (FR-008) — enforced by
intersecting any skill's `allowed-tools` with the agent's own `tools` list, never unioning.
Bundled executable scripts remain unsupported and must be flagged, not silently dropped
(FR-009). No real-time push from import sources — recheck is daily-cron plus manual refresh
(FR-021).

**Scale/Scope**: Single-user; spec's own scale target is "20+ imported skills manageable in
under 30s" (SC-005) — no scale engineering beyond straightforward indexed queries.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First Development** — PASS. This plan follows `specs/phases/114-agent-skills/spec.md`.
- **II. Single-User Model** — PASS. No `user_id`/tenancy on any new table; single API key gates
  all skill management REST routes, per spec Assumptions.
- **III. Layered Package Architecture** — PASS. `ze-skills` is a new `core/` package with no
  domain knowledge of a specific plugin's business logic; it depends only on `ze-agents`,
  `ze-proactive`, `ze-logging`, `ze-data` (mirrors `ze-worldstate`'s dependency list). It is
  wired directly by `apps/ze-api` (composition root), not as a `ZePlugin` — matching how
  `ze-worldstate`/`ze-automation` are wired, since skills are cross-cutting engine-adjacent
  infrastructure, not a single domain's concern. The new `ZePlugin.bundled_skill_paths()` hook
  (default `[]`) lets plugins register bundled skills without `ze-skills` importing any plugin
  package — same shape as `agent_module_paths()`. `SkillSource` for imported vs. bundled is a
  closed two-value enum owned by `ze-skills` itself (not a cross-plugin vocabulary concern);
  the *bundling plugin's identity* (e.g. `"ze-calendar"`) is carried as a plain string field,
  never a core-owned enum of plugin names — respecting the plugin-domain-vocabulary rule.
- **IV. Typed, Explicit Python** — PASS. `types.py` dataclasses (`Skill`, `SkillReview`,
  `ReferenceFile`), `StrEnum` for `SkillStatus`/`SkillSource`/`SkillTrigger`. New `ZeError`
  subclasses (`SkillParseError`, `SkillNotFoundError`, `InvalidSkillTransitionError`) in
  `errors.py`. All I/O async (`httpx.AsyncClient`, `asyncpg`).
- **V. Test Discipline** — PASS (planned). Tests in `core/ze-skills/tests/`; mock `httpx`
  responses for import/recheck, mock asyncpg pool for the store, mock the embedder for
  matching tests.
- **VI. Explicit Persistence** — PASS. Hand-written raw-SQL Alembic migrations under
  `core/ze-skills/ze_skills/migrations/versions/`, prefix `zsk`, registered in
  `apps/ze-api/ze_api/migrate.py`'s `_ZE_SKILLS_VERSIONS` constant alongside the other
  directly-wired core packages. No ORM.
- **VII. One LLM Gateway, Local Embeddings** — PASS. Skill matching uses the existing local
  embedder singleton (`ze_core.embeddings`) via injection — no new embedding model, no new LLM
  calls for matching. Import/parsing does not call an LLM at all (deterministic YAML +
  Markdown parsing).

No violations requiring Complexity Tracking justification.

**Post-Phase-1 re-check**: `data-model.md` and `contracts/skills-api.md` introduce no new
tables outside `ze-skills`' own migration chain, no ORM, no per-user columns, and no core enum
of plugin identities (`bundling_plugin` stays a plain string). Gate still PASSES after design.

## Project Structure

### Documentation (this feature)

```text
specs/phases/114-agent-skills/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output (REST + WS/trace contract)
│   └── skills-api.md
└── tasks.md              # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
core/ze-skills/                        # NEW core package (Layer: core, no domain knowledge)
├── pyproject.toml                     # deps: ze-agents, ze-proactive, ze-logging, ze-data, httpx, asyncpg
└── ze_skills/
    ├── __init__.py
    ├── types.py                       # Skill, SkillReview, ReferenceFile, SkillStatus,
    │                                   #   SkillSource, SkillTrigger, SkillMatch dataclasses
    ├── errors.py                      # SkillParseError, SkillNotFoundError, InvalidSkillTransitionError
    ├── parser.py                      # parse_skill_md() — YAML frontmatter + body, script-ref detection
    ├── importer.py                    # fetch_skill_source() — URL/archive fetch via httpx, zip extraction
    ├── store.py                       # SkillStore protocol + PostgresSkillStore
    ├── review.py                      # approve_skill, reject_skill, disable_skill, enable_skill,
    │                                   #   remove_skill — pending→resolved transitions (goal-suggestion-store shape)
    ├── matching.py                    # SkillMatcher — embeds active skill descriptions once,
    │                                   #   cosine-similarity per turn (EmbeddingRouter pattern) +
    │                                   #   /skill-name explicit-invocation parsing
    ├── rest.py                        # thin orchestration layer for REST routes, plain dicts out
    ├── jobs/
    │   ├── __init__.py
    │   └── recheck.py                 # SkillRecheckJob (@proactive_job, daily cron)
    ├── bootstrap.py                   # build_skills_stack(shared, settings), register_proactive_jobs()
    └── migrations/
        ├── env.py
        └── versions/
            └── zsk001_skills.py       # skills, skill_reference_files, skill_reviews tables

core/ze-core/ze_core/orchestration/nodes/skills.py   # NEW node: match_skills(state, config)
core/ze-core/ze_core/orchestration/graph.py           # add_node("match_skills", ...) after embed_route
core/ze-core/ze_core/orchestration/nodes/trace.py     # record_trace: populate MessageTrace.skills_used
core/ze-core/ze_core/conversation/messages/types.py   # MessageTrace.skills_used: list[SkillUsageTrace]

core/ze-agents/ze_agents/types.py                     # AgentContext: + active_skills, skill_tool_names
core/ze-agents/ze_agents/base_agent.py                # _build_system_prompt: prepend skill instructions;
                                                        # agentic_loop: intersect tool_names with skill_tool_names

core/ze-plugin/ze_plugin/plugin.py                     # ZePlugin.bundled_skill_paths() -> list[str], default []
core/ze-agents/ze_agents/bootstrap.py                  # import bundled skill modules at startup (mirrors
                                                        # _plugin_agent_module_paths)

apps/ze-api/ze_api/container.py                        # wire build_skills_stack(shared, settings), pass
                                                        # skill_matcher into orchestration configurable
apps/ze-api/ze_api/compose.py                          # register_skills_jobs(scheduler, settings, stack)
apps/ze-api/ze_api/migrate.py                          # _ZE_SKILLS_VERSIONS constant
apps/ze-api/ze_api/api/routes/skills.py                # GET/POST /api/v0/skills, /import, /{id}/approve,
                                                        # /{id}/reject, /{id}/disable, /{id}/enable, /{id}, /{id}/refresh
apps/ze-api/ze_api/api/app.py                          # app.include_router(skills.router, prefix="/api/v0")
apps/ze-api/ze_api/api/schemas.py                      # SkillResponse, SkillListResponse, SkillImportRequest, …
apps/ze-api/config/config.yaml                         # + `skills:` block (recheck cron, match threshold)

apps/ze-web/src/entities/skill/
├── api/useSkillsQuery.ts
├── api/useSkillImportMutation.ts
├── api/useSkillTransitionMutation.ts                  # approve/reject/disable/enable/remove
└── index.ts
apps/ze-web/src/widgets/skill-management/
└── ui/SkillManagementList.tsx                          # list + import + transitions (loop-review shape)
apps/ze-web/src/pages/skills/                           # management page, routed via nav-routes.ts
apps/ze-web/src/widgets/mind-panel/…                     # extend existing trace panel to render skills_used

core/ze-skills/tests/                                   # unit tests: parser, importer, matching, store, review
apps/ze-api/tests/…                                     # REST route tests
apps/ze-web/src/**/*.test.tsx                            # management widget tests
```

**Structure Decision**: New standalone `core/ze-skills/` package, directly wired (not a
`ZePlugin`) — same composition pattern as `ze-worldstate`, since skills are cross-cutting
engine-adjacent infrastructure consumed by every agent rather than one domain's concern. Graph
integration point is a single new orchestration node (`match_skills`) reading an injected
`SkillMatcher` from `config["configurable"]`, exactly mirroring how `surface_loops` consumes
`loop_surfacer` — this keeps `ze_core` free of any new package dependency on `ze_skills`.
Tool-narrowing and instruction-injection reuse the existing `AgentContext`/`agentic_loop`
extension points already proven by `resume_recap` (single-field addition + single consumption
site in `base_agent.py`) rather than touching every individual `@agent` class.

## Complexity Tracking

*No Constitution Check violations — table intentionally omitted.*
