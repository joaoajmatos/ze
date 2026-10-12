# Ze — Agent Guide

## What this is

Ze is a single-user personal AI assistant. A Python/FastAPI backend with a LangGraph
orchestration layer routes user messages to specialised agents (research, companion,
calendar, email, workflow). Users interact via a React web app over WebSocket.
Push notifications are delivered via ntfy. All LLM calls go through OpenRouter.

## Repository layout

```
ze/                           # monorepo root
├── core/                     # Shared infrastructure — no domain knowledge, grouped by role
│   ├── kernel/                # Pure infra leaves — ze-logging and ze-data have no Ze deps; ze-components depends on ze-agents
│   │   ├── ze-logging/         # structlog setup, get_logger, context binding
│   │   ├── ze-data/            # DataDomain, DataPortabilityService (no Ze deps)
│   │   └── ze-components/      # Server-driven UI component descriptors (depends on ze-agents)
│   ├── contracts/              # Developer-facing ABCs/protocols the engine implements against
│   │   ├── ze-agents/           # Developer API — BaseAgent, @agent, @tool, shared types
│   │   │   └── ze_agents/
│   │   │       ├── interface/   # AppInterface ABC, InputPreprocessor, validation, types
│   │   │       ├── progress/    # ProgressReporter, translations
│   │   │       ├── onboarding/  # Re-exports ze_onboarding types for agents
│   │   │       ├── base_agent.py # BaseAgent ABC with agentic_loop; optional routing_criteria (Choice text, falls back to description)
│   │   │       ├── claims.py    # Shared ClaimKind / Provenance / Confidence / decay() vocabulary
│   │   │       ├── client.py    # LLMClient Protocol
│   │   │       ├── db.py        # DBPool Protocol
│   │   │       ├── delegate.py  # delegate_to_agent — conductor fan-out to specialists
│   │   │       ├── errors.py    # Full ZeError hierarchy
│   │   │       ├── hooks.py     # HarnessHook ABC (agentic loop — not a plugin concern)
│   │   │       ├── registry.py  # @agent decorator + module-level agent registry
│   │   │       ├── settings.py  # Settings dataclass
│   │   │       ├── system_one.py # SystemOneClient Protocol — typed judgments (noul / choice / score)
│   │   │       └── tool.py      # @tool decorator, ToolAccess
│   │   ├── ze-communication/    # Channel contract — types, outbound/inbound ABCs, registry
│   │   │   └── ze_communication/
│   │   │       ├── types.py     # ChannelType, ChannelHandle, Message, SentMessage, Thread, InboundMessage
│   │   │       ├── channel.py   # Channel ABC (outbound), InboundChannel ABC
│   │   │       └── registry.py  # ChannelRegistry
│   │   ├── ze-plugin/           # Plugin extension framework — ZePlugin ABC, signals
│   │   │   └── ze_plugin/
│   │   │       ├── integration.py# ZeIntegration protocol
│   │   │       ├── plugin.py    # ZePlugin ABC + DataDomain
│   │   │       ├── registry.py  # plugin registry (_registry, get_plugin_registry)
│   │   │       └── signals.py   # SignalSource protocol
│   │   └── ze-proactive/        # Job scheduling framework
│   │       └── ze_proactive/    # ProactiveJob, ProactiveScheduler, ProactiveNotifier, PushLogStore
│   ├── engine/                 # The orchestration engine itself
│   │   └── ze-core/             # Engine — routing, orchestration, telemetry, DI container
│   │       └── ze_core/
│   │           ├── capability/  # CapabilityGate, PostgresCapabilityOverrideStore, modes
│   │           ├── conversation/# invoke_raw_turn (turn.py) — streamed graph turn entry point; retry.py (Retry eligibility), rewind.py
│   │           ├── openrouter/  # OpenRouterClient, System One client (engine internal — plugins use the Protocols)
│   │           ├── orchestration/# graph_builder, graph nodes, AgentState, edges, judgment_state (shared System One state)
│   │           ├── routing/     # EmbeddingRouter, ComplexityEstimator, fallback, store
│   │           ├── telemetry/   # CostTracker, CostReconciler, PostgresCostStore, ContextVar
│   │           ├── container.py # Base Container with DI wiring and invoke/resume entry points
│   │           ├── embeddings.py # Shared intfloat/multilingual-e5-base singleton
│   │           └── nli.py       # NLI cross-encoder (NLIClient implementation)
│   ├── seam/                   # Cross-cutting substrate consumed by every domain layer below
│   │   └── ze-collision/        # Contribution collision detection — cross-function conflict logging
│   │       └── ze_collision/
│   │           ├── types.py     # CollisionCandidate, CollisionLogEntry
│   │           ├── store.py     # CollisionLogStore Protocol + PostgresCollisionLogStore
│   │           ├── detect.py    # submit_and_detect_collisions() wrapper over validate_and_submit
│   │           ├── rest.py      # list_collisions() query surface
│   │           └── migrations/  # zcol001 (contribution_collisions)
│   ├── cognition/               # Memory, correlation, world-state — the "mind" substrate
│   │   ├── ze-memory/            # Memory — facts, episodes, graph, retrieval, feedback_records/ (reply feedback evidence)
│   │   ├── ze-correlation/       # Cross-domain hypothesis formation
│   │   └── ze-worldstate/        # Open-loop substrate — active concerns, honest provenance, evidence-linked confidence
│   │       └── ze_worldstate/
│   │           ├── types.py     # OpenLoop, LoopState, LoopClaimKind, LoopProvenance
│   │           ├── store.py     # LoopStore Protocol + PostgresLoopStore
│   │           ├── matching.py  # entity-overlap + embedding-similarity dedup
│   │           ├── decay.py     # confidence decay cascade, called at the evidence-writing code path
│   │           ├── extraction.py # conservative relevance-gated loop extraction (109 Haiku gate = fallback)
│   │           ├── loop_judge.py # System One loop gate — three Nouls, bars, pure decide()
│   │           ├── admission.py  # LoopInflow — gate + Haiku title writer + commit
│   │           ├── review.py    # confirm/close/drop lifecycle transitions
│   │           ├── inflow.py    # inflow wiring helpers (conversation hook, messenger/calendar/ingestion extractors)
│   │           ├── jobs/        # stale-suspicion expiry job
│   │           └── migrations/  # zw001 (open_loops), zw002 (drift columns)
│   ├── automation/              # Goals, workflows, skills — built on cognition
│   │   ├── ze-automation/        # Core automation engine — goals, workflows, accountability, planners, executors, agents
│   │   │   └── ze_automation/
│   │   │       ├── goals/       # GoalStore, GoalPlanner, GoalExecutor, PostgresGoalStore, GoalSuggestionStore, types
│   │   │       ├── workflow/    # WorkflowStore, WorkflowPlanner, WorkflowScheduler, PostgresWorkflowStore, types
│   │   │       ├── accountability/ # AccountabilityStore, ActivitySummary, AnomalyRecord, build_narrative
│   │   │       ├── agents/      # GoalAgent, WorkflowManagerAgent
│   │   │       ├── jobs/        # goal/workflow/accountability proactive jobs
│   │   │       ├── runtime/     # AutomationPlanner, AutomationStore contracts
│   │   │       └── migrations/  # zc006–zc009 (goal traces/suggestions/stuck/reuse), zc011 (workflows), zc014 (accountability),
│   │   │                        # zc021/zc025 (workflow execution summary/snapshot), zc026 (workflow revisions), zc030 (goal learning claims), zc031 (message supersession)
│   │   └── ze-skills/            # Agent Skills — import, review, matching, tool-narrowing
│   │       └── ze_skills/
│   │           ├── types.py     # Skill, SkillReview, ReferenceFile, SkillStatus/Source/Trigger
│   │           ├── store.py     # SkillStore Protocol + PostgresSkillStore
│   │           ├── parser.py    # parse_skill_md — YAML frontmatter + Markdown body
│   │           ├── importer.py  # fetch_skill_source — URL/zip fetch
│   │           ├── matching.py  # SkillMatcher — embedding similarity + /skill-name
│   │           ├── judge.py     # System One skill gating — shortlist, Choice/Noul questions, surface config, decide()
│   │           ├── review.py    # approve/reject/disable/enable/remove/refresh
│   │           ├── jobs/        # SkillRecheckJob (daily source-content recheck)
│   │           └── migrations/  # zsk001 (skills), zsk002 (skill_scripts + executable approval)
│   ├── arbitration/             # Consumes cognition + automation to rank/order attention
│   │   └── ze-priority/          # PriorityView + shared push budget + user-directed priority override
│   └── ops/                     # Environment, onboarding, ingestion, seed data, eval
│       ├── ze-workspace/         # Isolated computer — files, shell, skill scripts
│       │   └── ze_workspace/
│       │       ├── client.py    # WorkspaceClient HTTP to sidecar
│       │       ├── gate.py      # WorkspaceGate (action × origin; no execution modes since phase 161)
│       │       ├── tools.py     # workspace_* @tools (not imported by ze-core/ze-agents)
│       │       ├── store.py     # workspace_state + workspace_runs
│       │       └── migrations/  # zws001 (workspace_state, workspace_runs) … zws005 (drop workspace mode)
│       ├── ze-onboarding/        # Onboarding sessions/steps/seeds
│       ├── ze-ingestion/         # Ingestion pipeline — fetchers, classifier, memory sink; registers ze-yt's fetcher when installed
│       ├── ze-seed/              # Dev data seeding
│       └── ze-eval/              # Eval infrastructure — runner, judge, verifier, MCP server
├── packages/                 # Shared packages (Python SDK + frontend npm)
│   ├── ze-sdk/               # Public SDK surface — flat re-export layer for plugin authors
│   │   └── ze_sdk/           # ze_sdk, ze_sdk.types, ze_sdk.proactive, ze_sdk.channels,
│   │                         # ze_sdk.memory, ze_sdk.errors, ze_sdk.automation, ze_sdk.contribution,
│   │                         # ze_sdk.correlation, ze_sdk.onboarding, ze_sdk.ui
│   ├── ze-client/            # @myguyze/ze-client — typed REST SDK + WS types for ze-web
│   └── ze-ui/                # @myguyze/ze-ui — server-driven UI contract + React renderer
├── plugins/                  # ZePlugin domain extensions
│   ├── ze-personal/          # Personal-assistant domain layer (ZePlugin) — persona, contacts, onboarding
│   │   └── ze_personal/
│   │       ├── contacts/     # PersonStore, ContactChannelStore, consolidator, extractors, tools
│   │       ├── persona/      # PostgresPersonaStore, identity builder, types
│   │       ├── agents/       # research, companion agents (goal/workflow agents live in ze-automation)
│   │       ├── jobs/         # briefing, insights, contacts jobs
│   │       └── plugin.py     # PersonalPlugin(ZePlugin) — wires persona + contacts into graphs
│   ├── ze-messenger/         # Cross-channel messenger agent (ZePlugin)
│   │   └── ze_messenger/
│   │       ├── agents/messenger/ # MessengerAgent + Gmail tools
│   │       └── plugin.py     # MessengerPlugin(ZePlugin)
│   ├── ze-calendar/          # Calendar, reminders, and timezone domain (ZePlugin)
│   │   └── ze_calendar/
│   │       ├── agents/       # CalendarAgent, RemindersAgent + tools
│   │       ├── reminders/    # ReminderStore, CalendarReminderService, CalendarReminderStore
│   │       ├── jobs/         # CalendarReminderJob
│   │       ├── timezone/     # TimezoneService, world_time @tool
│   │       └── plugin.py     # CalendarPlugin(ZePlugin) — registers agents
│   ├── ze-prospecting/       # Prospecting agent, campaign store, recovery job (ZePlugin)
│   │   └── ze_prospecting/
│   │       ├── agents/       # ProspectingAgent + tools
│   │       ├── jobs/         # recover_stale_campaigns
│   │       ├── store.py      # ProspectCampaignStore
│   │       └── plugin.py     # ProspectingPlugin(ZePlugin)
│   ├── ze-news/              # News fetching, RSS sources, NewsAgent, NewsPlugin
│   └── ze-finance/           # Finance domain (ZePlugin) — Trading212 + CSV sources, FinanceAgent, recurring detection
├── integrations/             # External service wrappers — no Ze domain knowledge
│   ├── ze-google/            # Google OAuth2 credentials, service client factories, GmailChannel
│   ├── ze-browser/           # Browser sidecar client (BrowserClient + tool)
│   ├── ze-notifications/     # Push notification abstraction (ntfy)
│   ├── ze-trading212/        # Trading212 REST API v0 client (Trading212Client) — used by ze-finance
│   └── ze-yt/                # yt-dlp audio fetcher (YtDlpFetcher) for video URLs — used by ze-ingestion
├── apps/                     # Deployment units
│   ├── ze-api/               # HTTP/WebSocket API, wires all plugins
│   │   ├── ze_api/
│   │   │   ├── api/          # FastAPI app, WebSocket endpoint, REST routes
│   │   │   ├── interface/    # NativeAppInterface (WebSocket + ntfy delivery)
│   │   │   ├── migrations/   # Alembic env.py + meta-runner entry (no owned tables)
│   │   │   ├── compose.py    # Proactive job registration fan-out
│   │   │   ├── container.py  # ZeContainer (registers all ZePlugins)
│   │   │   ├── migrate.py    # Meta-runner: discovers all package migration paths
│   │   │   └── settings.py   # ZeApiSettings (shell env + YAML)
│   │   ├── config/
│   │   │   ├── config.yaml   # Models, contacts, proactive schedules (secrets in .env)
│   │   │   └── persona.yaml  # Persona profiles and dials
│   │   └── tests/
│   └── ze-web/               # React web client (Vite + TypeScript + Tailwind + shadcn/ui)
├── sidecar/                  # Docker sidecars: browser/ (Playwright), workspace/ (isolated computer)
├── eval/                     # Eval test data and entrypoints (uses core/ops/ze-eval)
│   ├── scenarios/            # YAML scenario definitions — edit these to add tests
│   ├── calibration/          # System One calibration sets + runner (make calibrate-speech-act)
│   ├── results/              # JSON run outputs (gitignored)
│   ├── run.py                # CLI: python eval/run.py [--judge] [--tag X] [report]
│   └── server.py             # MCP server: python eval/server.py
├── specs/                    # Design specs — spec-kit feature dirs in phases/, plus core/ and arch/
├── docs/                     # architecture.md, configuration.md, …
└── Makefile                  # make test, make test-core, make dev, …
```

### Package dependency graph

Declared `ze-*` dependencies from each package's `pyproject.toml`:

```
ze-logging        (no ze deps)             core/kernel/
ze-data           (no ze deps)             core/kernel/
ze-components   → ze-agents                core/kernel/
ze-agents       → ze-logging, ze-onboarding  core/contracts/  ← cycle: ze-agents ↔ ze-onboarding
ze-communication→ ze-agents                core/contracts/  ← channel types, ABCs, registry
ze-plugin       → ze-agents, ze-data, ze-logging  core/contracts/
ze-proactive    → ze-agents, ze-logging    core/contracts/
ze-core         → ze-agents, ze-communication, ze-components, ze-data, ze-logging, ze-memory, ze-plugin  core/engine/  ← engine; never a plugin dep
ze-collision    → ze-agents, ze-plugin, ze-logging  core/seam/  ← contribution collision detection; wired by ze-api directly
ze-memory       → ze-agents, ze-plugin, ze-collision, ze-logging  core/cognition/  ← ze-plugin: Contribution seam (Signal write path)
ze-correlation  → ze-agents, ze-logging, ze-memory, ze-plugin, ze-collision  core/cognition/  ← cross-domain hypothesis formation; ze-plugin: Contribution seam
ze-worldstate   → ze-agents, ze-proactive, ze-memory, ze-data, ze-components, ze-correlation, ze-plugin, ze-collision, ze-logging  core/cognition/  ← open loops; wired by ze-api directly; ze-plugin: Contribution seam (loop write path)
ze-automation   → ze-agents, ze-proactive, ze-memory, ze-components, ze-data, ze-logging  core/automation/  ← goals + workflows; wired by ze-api directly
ze-skills       → ze-agents, ze-proactive, ze-logging, ze-data, ze-memory  core/automation/  ← agent skills; wired by ze-api directly
ze-priority     → ze-agents, ze-proactive, ze-worldstate, ze-automation, ze-correlation, ze-plugin, ze-collision  core/arbitration/  ← attention arbitration (PriorityView + shared push budget) + user-directed priority override; wired by ze-api directly; ze-plugin: Contribution seam (reprioritization write path)
ze-workspace    → ze-agents, ze-logging, ze-data, ze-memory, ze-plugin  core/ops/  ← isolated computer; wired by ze-api; ze-core/ze-agents must not import it
ze-onboarding   → ze-agents, ze-memory     core/ops/  ← cycle: ze-onboarding ↔ ze-agents
ze-ingestion    → ze-agents, ze-browser, ze-logging, ze-memory  core/ops/  ← imports ze_yt optionally (try/except ImportError)
ze-seed         → ze-automation, ze-core, ze-logging, ze-memory, ze-onboarding  core/ops/
ze-eval           (no ze deps — HTTP only) core/ops/  ← eval infrastructure
ze-sdk          → ze-agents, ze-automation, ze-collision, ze-communication, ze-correlation, ze-data, ze-logging, ze-memory, ze-onboarding, ze-plugin, ze-proactive  packages/  ← plugin entry point
ze-browser      → ze-core                  integrations/  ← code imports only ze_agents
ze-notifications  (no ze deps)             integrations/
ze-trading212     (no ze deps)             integrations/
ze-google       → ze-communication         integrations/  ← GmailChannel now lives here
ze-yt           → ze-ingestion             integrations/  ← also imports ze_logging (undeclared)
ze-personal     → ze-sdk, ze-news, ze-automation, ze-priority, ze-components, ze-seed   plugins/
ze-messenger    → ze-sdk, ze-google, ze-personal            plugins/
ze-prospecting  → ze-sdk, ze-browser, ze-personal           plugins/
ze-calendar     → ze-sdk, ze-google, ze-personal, ze-components, ze-seed   plugins/
ze-news         → ze-sdk, ze-personal, ze-components        plugins/  ← cycle: ze-personal ↔ ze-news
ze-finance      → ze-sdk, ze-ingestion, ze-trading212       plugins/
ze-api          → ze-automation, ze-browser, ze-calendar, ze-collision, ze-components, ze-core, ze-correlation, ze-data,
                    ze-finance, ze-google, ze-ingestion, ze-logging, ze-memory, ze-messenger, ze-news, ze-notifications,
                    ze-onboarding, ze-personal, ze-priority, ze-prospecting, ze-seed, ze-skills, ze-workspace, ze-worldstate, ze-yt   apps/
ze-web            (React — connects to ze-api over WebSocket, no Python deps)         apps/
```

Known drift from the import rules below (code, not yet fixed): `ze-personal` and
`ze-news` import `ze_core` (orchestration state/graph, `OpenRouterClient`);
`ze-messenger` and `ze-seed` import `ze_api`; plugins import `ze_memory` internals
(`policies`, `admission`, `relevance`, `extractor`, `bootstrap`, `graph.*`) that `ze_sdk`
does not yet re-export. No plugin imports `ze_plugin` directly any more
(`ze_sdk.contribution`, `ze_sdk.memory`, `ze_sdk.api`).

## Essential commands

```bash
make help            # full target list

# Setup
make install         # Python workspace deps (uv sync)
make web-install     # JS workspace deps — ze-web, @myguyze/ze-ui, @myguyze/ze-client (bun install at repo root)

# Database
make db-up           # start Postgres via Docker
make migrate         # apply migrations from all packages (requires db-up first)
make migrate-stamp   # one-time stamp for existing DBs after migration restructure

# Development
make dev             # backend (uvicorn --reload on :8000) + workspace sidecar; auto-migrates and seeds dev data
make web             # React web app — bun dev on :5173
make dev-full        # backend + web app together; Ctrl-C stops both
make logs            # tail the server log file

# Testing
make test            # ze-api tests (skips slow embedding tests)
make test-<name>     # any package — see docs/testing.md
make test-py         # every Python package suite; reports all failures (CI gate)
make test-all        # test-py with slow tests, then test-web
make test-web        # @myguyze/ze-ui + React web app (vitest)
make typecheck-web   # tsc --noEmit for ze-web and @myguyze/ze-ui

# Code quality
make lint            # ruff lint across the repo (ruff.toml excludes .claude/)
make format          # ruff format + fix across all Python packages

# Evals
make dev-eval        # backend for evals — no dev seed data, PUBLIC_URL cleared (background jobs still start)
make eval-server     # start MCP eval server (requires dev-eval running; see docs/eval.md)
make calibrate-speech-act  # LIVE System One run over eval/calibration/speech_act.jsonl; costs credits
make calibrate-routing     # LIVE System One run over eval/calibration/routing.jsonl; costs credits
make calibrate-skills      # LIVE System One run over eval/calibration/skills.jsonl; costs credits (--recall: offline shortlist recall)
make calibrate-loop-gate  # LIVE System One + Haiku baseline over eval/calibration/loop_gate.jsonl; costs credits (--set holdout = the one verdict run; --check-sets offline)
```

## Stack decisions (do not relitigate without reading specs/)

| Layer | Choice | Reason |
|---|---|---|
| LLM gateway | OpenRouter only | Single billing, easy model swap |
| Web search | OpenRouter `openrouter:web_search` server tool | No separate search API key; LLM decides when to search; billed via OpenRouter credits |
| Embeddings | intfloat/multilingual-e5-base local (`query:` / `passage:`) | No API cost, multilingual, 768-dim |
| Orchestration | LangGraph + AsyncPostgresSaver | Graph persistence survives restarts |
| DB driver | asyncpg (runtime), psycopg2 (Alembic CLI) | asyncpg has no sync mode |
| Config | Pydantic BaseSettings + YAML files | Secrets in .env, structure in YAML |
| Migrations | Alembic raw SQL, no ORM | Explicit schema control |
| Client interface | React + WebSocket | Browser-first SPA; Tauri desktop wrapper deferred |
| Push notifications | ntfy | Self-hostable, no vendor lock-in, deep-link support |
| Compatibility | None until v1 | Never deployed; hard-cut rather than shim. See constitution Principle VIII and `specs/arch/pre-v1-hard-cuts.md` |

## Coding conventions

### Python

- **Types**: dataclasses for domain types, Pydantic only in `ze_api/api/schemas.py`.
  Never use Pydantic models inside domain modules — use `types.py` dataclasses.
- **File naming**: `types.py` everywhere (never `models.py` — avoids ORM confusion).
- **DI**: Constructor injection in all classes; FastAPI `Depends()` only in `ze_api/api/`.
  No module-level globals that hold mutable state (except the `lru_cache` singletons
  in `settings.py` and `embeddings.py`).
- **OpenAPI**: Every REST route must declare `response_model`, `summary`, and
  `description`; request/query params use Pydantic or annotated `Query`. See
  `specs/phases/007-api/spec.md`.
- **Logging**: Always use `get_logger(__name__)`. Never use `print()` or stdlib
  `logging` directly.
- **Errors**: Raise from `ze_api/errors.py` or `ze_sdk/errors.py`. Never raise bare
  `Exception` or `ValueError` in domain code — always use a typed subclass of `ZeError`.
- **Async**: All I/O is async. Fire-and-forget tasks use `asyncio.create_task()`.
  Never `asyncio.run()` inside a running event loop.
- **Comments**: Default to none. Only add a comment when the *why* is non-obvious.
- **Pre-v1**: Until a versioned v1, break APIs and schemas when the design is wrong.
  Do not add compatibility shims, dual-write, or wrap-then-replace across phases.
  See constitution Principle VIII and `specs/arch/pre-v1-hard-cuts.md`.
- **Imports**: Plugin code imports from `ze_sdk.*` (agent API, types, proactive, memory,
  channels, errors, automation). Automation types (goals, workflows) from `ze_automation.*`
  or `ze_sdk.automation`. Contact/persona domain from `ze_personal.*`. Calendar/reminder
  domain from `ze_calendar.*`. Google credentials from `ze_google.*`. Engine internals
  (`ze_core.*`) are for `ze_api/` and `ze_core/` only — never import `ze_core` from a
  plugin package. Never import from `ze_plugin.*` directly in plugin code — always go
  through `ze_sdk.*`; `ze_plugin` is for engine and SDK use only.

# Testing

- Tests live in `<package>/tests/` (Python) or `src/**/*.test.ts(x)` (ze-web).
- Run from the **repo root** via `make test-<short-name>`. See [docs/testing.md](docs/testing.md).
- `asyncio_mode = "auto"` — all async tests just work, no `@pytest.mark.asyncio`.
- No real DB in unit tests. Mock asyncpg pools with `AsyncMock`.
- No real OpenRouter calls. Mock `client.complete` and `client.stream`.
- Settings fixtures: copy real YAML files to `tmp_path`, construct `Settings` with
  `config_dir=tmp_path/config`. Never monkey-patch Pydantic internals.
- Embedder in tests: use `make_embedder(agent_vecs, prompt_vec)` pattern (dict-keyed,
  sorted alphabetically) to match production load order.
- Slow tests (embedding model): mark with `@pytest.mark.slow`, skipped by default.
  Pass `SLOW=1` (e.g. `make test-core SLOW=1`) or run `make test-all`.

### ze-web (React / FSD)

`apps/ze-web/src/` follows **Feature-Sliced Design**. Layer order (higher may import lower, never reverse):

```
pages → widgets → features → entities → shared
```

**Query hooks** — always in `entities/<name>/api/use<Name>Query.ts`, exported from `entities/<name>/index.ts`. Widgets import from the entity index, never call SDK directly.

**Mutations** — entity-bound mutations in `entities/<name>/api/use<Name>Mutation.ts`; side-effect features (delete, export) in `features/<name>/api/use<Name>.ts`.

**Format / util helpers** — in `<slice>/lib/format.ts` within the slice that owns them. Do not add to `shared/lib/` unless used by ≥ 2 unrelated slices.

**SDK types** — import `type { Foo }` directly from `@myguyze/ze-client` in any layer; no re-export wrapper needed.

**Tailwind opacity** — non-standard steps must use arbitrary-value syntax: `bg-white/[0.03]` not `bg-white/3`. Standard steps (5, 10, 15, 20 …) use the shorthand form.

**Routes** — core-owned routes declared in `shared/config/nav-routes.ts` + `app/router/routes.ts`. Plugin routes injected at runtime via `GET /api/v0/ui/manifest`.

### Native app interface

- The `NativeAppInterface` in `ze_api/interface/native.py` handles all outbound delivery:
  WebSocket frames when the client is connected, ntfy push notifications otherwise.
- The WebSocket endpoint lives at `/ws`. One connection at a time — a new connection
  displaces the previous one with close code `4000`.
- On connect, unread messages are replayed from `MessageStore` before new frames flow.
- Confirmation requests are sent as `{"type": "confirmation", ...}` frames; the client
  replies with `{"type": "confirm", "id": "...", "choice": "approve"|"deny"|"edit"}`.
- `ConnectionManager` is on `app.state.connection_manager`; never instantiate it outside the lifespan.

## Configuration files

### `apps/ze-api/.env` (create from `apps/ze-api/.env.example`, never commit)
```
OPENROUTER_API_KEY=sk-or-...
ZE_API_KEY=your-secret-key
DATABASE_URL=postgresql://ze:ze@localhost:5432/ze
DATABASE_URL_SYNC=postgresql+psycopg2://ze:ze@localhost:5432/ze
NTFY_BASE_URL=https://ntfy.sh
NTFY_TOPIC=ze-your-topic
NTFY_TOKEN=your-ntfy-token
PUBLIC_URL=https://ze.fly.dev
LOG_LEVEL=INFO
CONFIRM_TIMEOUT_SECONDS=900
```

### `apps/ze-api/config/config.yaml`
Structural config: model assignments, contacts consolidation settings, proactive
schedules. Agent config (description, model, intents) lives on
`@agent` class attributes in Python — not in YAML.

Hot-reloaded on SIGHUP without restart.

## Adding a new agent

1. Write a spec first via spec-kit: `/speckit-specify` creates `specs/phases/NNN-<name>/spec.md` (see `specs/README.md` for the pipeline and index).
2. Create the agent in the appropriate package — `ze_personal/agents/`, `ze_messenger/agents/`,
   `ze_prospecting/agents/`, or `ze_calendar/agents/` — decorate with `@agent` from
   `ze_sdk`, subclass `BaseAgent` from `ze_sdk`.
   Put `description`, `model`, `intents`, `tools`, and `timeout` as class
   attributes. Define `_AGENT_INSTRUCTIONS` at the top.
3. Add a `tools.py` alongside the agent if it needs Python tools. Use `@tool` from
   `ze_sdk`. Use `"openrouter:web_search"` in `tools` for web search —
   no Python tool needed.
4. Add the module paths to the package's `ZePlugin.agent_module_paths()` — tools module
   first, then the agent module. The bootstrapper imports these at startup to fire `@agent`
   and `@tool` registration. No other wiring needed.
5. Write tests in `tests/agents/<name>/`.

See `docs/adding-an-agent.md` for the full authoring guide.

## Adding a new plugin

1. Create a `ZePlugin` subclass in `<package>/plugin.py`.
2. Declare the plugin via an entry point in the package's `pyproject.toml`:
   ```toml
   [project.entry-points."ze.plugins"]
   ze_myplugin = "ze_myplugin.plugin:MyPlugin"
   ```
3. Add the package to `apps/ze-api/pyproject.toml` dependencies.
4. Override `startup(container)` and `shutdown()` for async lifecycle needs.
5. Implement `memory_policies()` and `checkpoint_serde_modules()` when the plugin
   adds agents or checkpointed domain types.
6. If the plugin owns database tables, add a `migrations/` directory and override
   `migrations_path()` — see "Migration ownership" below.

Plugin discovery, topological ordering, and graph hook merging are automatic.
Add types to `plugin_deps` in `ze_api/container.py` only when the plugin
constructor needs a shared service not already in the dep map (phase 47b).

## Migration ownership

Every package that owns database tables owns its own Alembic migration chain.
`ze_api/migrate.py` is a meta-runner: it discovers all chains via `version_locations`
and runs them against a single `alembic_version` table.

| Package | Branch prefix | Tables |
|---|---|---|
| ze-core | `zc` | user_facts, episodes, user_profile, routing_log, llm_cost_log, goals, goal_milestones, goal_gates, persona_state, capability_overrides, LangGraph checkpoints, messages, sessions, pending_confirmations |
| ze-automation | `zc` (continues ze-core chain) | goal_execution_traces, goal_suggestions (stuck goals col, reuse hint col), workflows, workflow_executions, workflow_revisions, accountability_anomalies, goal_learning_* (`zc030`; drops the old goal_learnings) |
| ze-personal | `zc` (continues ze-automation chain) | contacts, contact_channels, contact_sources, insights, episodes.contacts_extracted, user_channels, user_channel_watermarks, thread_channel_map (contact_relationships dropped in `zc029`) |
| ze-memory | `zm` | memory_entities, memory_facts, memory_episodes, memory_events, memory_task_state, memory_profile_facets, memory_relationships, memory_signals, memory_session_summaries, memory_retrieval_cache, memory_dream_*, memory_episode_metadata, action_records, procedure_* (`zm022`–`zm023`; replace memory_procedures), feedback_records (`zm024`) |
| ze-onboarding | `zo` | onboarding_sessions, onboarding_steps, onboarding_seeds |
| ze-correlation | `zcor` | correlation_hypothesis |
| ze-worldstate | `zw` | open_loops |
| ze-proactive | `zpro` | push_log, notifications |
| ze-ingestion | `zi` | ingested_content |
| ze-calendar | `zcal` | calendar_reminders, user_reminders |
| ze-prospecting | `zpros` | prospect_campaigns, prospect_outreach |
| ze-messenger | `zmsg` | messenger_outbound_sends |
| ze-news | `zn` | news_articles |
| ze-finance | `zfin` | finance_accounts, finance_positions, finance_transactions, finance_csv_mappings, finance_recurring, finance_recurring_staleness |
| ze-skills | `zsk` | skills, skill_reference_files, skill_reviews, skill_scripts (`zsk002`) |
| ze-workspace | `zws` | workspace_state, workspace_runs |
| ze-collision | `zcol` | contribution_collisions |
| ze-priority | `zpri` | priority_overrides |

**Naming conventions:**
- One prefix per package (`zc`, `zm`, `zcal`, …). Exception: ze-core, ze-automation, and ze-personal share one `zc` chain.
- Filename: `{revision}_{feature}.py` — never phase names.
- Revision ID matches the filename prefix. Exception: five early ze-core files
  (`001`–`004`, `010`) predate the rule; their revision IDs are `zc001`–`zc004`, `zc010`.
- Migrations live in the package that owns the Postgres store.

**Rules:**
- ze-api runs migrations but owns no tables.
- Never add plugin-owned tables to ze-api migrations.
- For `ZePlugin` subclasses: create `<pkg>/migrations/` and override `migrations_path()` — the runner discovers it automatically.
- For non-plugin core packages (ze-core, ze-memory, ze-onboarding, ze-correlation, ze-proactive, ze-ingestion, ze-automation, ze-worldstate, ze-skills, ze-workspace, ze-collision, ze-priority): add an explicit `_ZE_*_VERSIONS` constant in `ze_api/migrate.py`.
- Use `depends_on` in migration files for cross-package ordering (e.g. ze-prospecting depends on `zc005` for the contacts table).

## LangGraph graph flow

```
preprocess (voice → transcript, image → caption) → [inject_routing_context, when a plugin adds a pre_route_node]
  → embed_route → (compound?) → decompose → fetch_context → match_skills → capability_check
                ↘ fetch_context ↗

capability_check → execute_tool ⇄ await_subtask_confirmation  (per-subtask gates)
                   execute_tool → correlate → surface_loops → (compound?) → synthesize → record_trace → write_memory → END
                                                                          ↘ record_trace ↗
                 → draft_response → await_confirmation  (graph pauses here: interrupt_before)
                                    await_confirmation → execute_tool | record_trace
                 → END (blocked)
```

- Graph builder: `ze_core/orchestration/graph.py`; conditional edges in `edges.py`.
- Graph state: `AgentState` in `ze_core/orchestration/state.py`.
- Dependencies injected via `config["configurable"]` at invocation time (not build time).
- Turns run through `invoke_raw_turn` (`ze_core/conversation/turn.py`), which uses
  `graph.astream_events()`: partial `trace_update` frames go out as nodes finish, and
  agent tokens reach the client as `{"type": "token"}` frames via `config["configurable"]["token_sink"]`.
- Confirmation resume: `graph.ainvoke(Command(resume=...), config)` when the graph holds an
  interrupt payload, else `graph.ainvoke(None, config)`, with the same `thread_id`.

## Phase status

| Phase | Scope | Status |
|---|---|---|
| 1 | Routing, research + companion agents, orchestration, API | Implemented |
| 2 | Memory — contradiction detection, episode summarisation, semantic retrieval | Implemented |
| 3 | Calendar + email agents, Google OAuth2 | Implemented |
| 4 | Workflow agent, multi-step planning, Postgres-persisted scheduler | Implemented |
| 5 | Memory consolidation — dedup facts, expire stale, summarise episodes | Implemented |
| 6 | User profile — synthesise facts + episodes into a structured portrait | Implemented |
| 7 | Proactive Ze — morning briefing, workflow failure alerts, calendar reminders | Implemented |
| 8 | Insight engine — weekly synthesis of facts + episodes into actionable insights | Implemented |
| 9 | Cost telemetry — per-flow/agent token tracking, automatic cost reconciliation | Implemented |
| 10 | Multimodal input — voice transcription + image/vision support | Implemented |
| 11 | Persona profiles + dials — named profiles, TARS-style numeric dials | Implemented |
| 12 | Contacts — person tracking, extraction from email/calendar/conversation, confirmation flow | Implemented |
| 13 | Reminders agent — NL time parsing, APScheduler firing, startup replay | Implemented |
| 14 | Progress messages — per-agent status messages, locale keys, atomic delete | Implemented |
| 15 | Introspection commands — costs, memory, contacts | Implemented |
| 16 | Agentic tool loop — LLM-driven ReAct loop in `BaseAgent`, calendar + email migrated | Implemented |
| 17 | Prospecting agent — autonomous target research, browser sidecar, outreach drafting | Implemented |
| 18 | Communication channel abstraction — `Channel` ABC, `EmailChannel`, contact channel handles | Implemented |
| 19 | Goal Engine — autonomous multi-week goal execution, verification gates, milestone loop | Implemented |
| 20 | Package architecture reorg — ze_core pure infra, ze-personal domain layer, ZePlugin ABC | Implemented |
| 21 | Agent harness — hook points, step-level abort, multi-agent handoffs | Implemented |
| 22 | Harness adoption — tool-call cap hook, research delegation, cancel command | Implemented |
| 23 | Goal engine v2 — milestone context injection, execution traces, adaptive replanning, enriched gate narrative | Implemented |
| 24 | Goal collaboration — goal-aware routing, conversational steering, post-goal retrospective, weekly narrative job | Implemented |
| 25 | Proactive goal suggestions — weekly LLM-generated goal proposals | Implemented |
| 26 | Stuck goal detection — idle milestone/gate alerts, recovery actions | Implemented |
| 27 | Cross-goal output reuse — prior milestone summaries injected into planner and executor prompts | Implemented |
| 28 | Cross-goal learning promotion — generalizable facts extracted from goal learnings and promoted to user memory on completion | Implemented |
| 44 | Calendar package split — ze-google (credentials), ze-calendar (agents, reminders, timezone), ze renamed to ze-api | Implemented |
| 45 | Native app interface — React web client, WebSocket transport, ntfy push notifications, ze-notifications + ze-components packages | Implemented |
| 46 | Accountability layer — weekly narrative, cost anomaly detection, confirmation persistence + replay + ntfy + timeout, `/status` command | Implemented |
| 48 | Core split — ze-agents (developer API), ze-proactive (job framework) extracted from ze-core | Implemented |
| 49 | Ze SDK — `ze-sdk` flat re-export layer; plugins import from `ze_sdk.*`, no direct ze-core dep | Implemented |
| 52 | Session-grouped episode consolidation — group episodes by session before archiving, one LLM summary per session | Implemented |
| 54 | Progress messages — plugin-local locale files, `ProgressTranslations.build()`, reporter wired end-to-end, `typing` frame carries text, `news.fetching` key for refresh | Implemented |
| 57 | Correlation engine — `ze-correlation` package, `CorrelationEngine`, `PostgresHypothesisStore`, graph neighbourhood expansion, recall guarantee, signal pinning | Implemented |
| 60 | Cross-plugin signal contract — `SignalSource` protocol, `ZePlugin.signal_sources()` hook, `NewsSignalSource`, `CalendarSignalSource`, container collection + dedup | Implemented |
| 64 | Plugin package extraction — `ze-plugin` package carved from `ze-agents`; `ZePlugin`, `channels/`, `SignalSource`, `ZeIntegration` in their own package; `ze-agents` focused on agent execution API | Implemented |
| 68 | ze-data — `DataDomain` and `DataPortabilityService` extracted from `ze-plugin`/`ze-api` into `core/kernel/ze-data`; no Ze deps | Implemented |
| 70 | Finance recurring detection — algorithmic recurring expense/subscription detection, staleness-aware proactive job, CSV nudge flow, price-change resurface | Implemented |
| 71 | Cross-goal awareness — convergence detection at goal creation, proactive reuse surfacing at milestone completion | Implemented |
| 72 | API client codegen — `@myguyze/ze-client` npm package generated from OpenAPI spec via `@hey-api/openapi-ts`; named SDK methods (`listContacts()`, etc.); WS types from `json-schema-to-typescript` | Implemented |
| 73 | API surface cleanup — all routes under `/api/v0/`; `HTTPBearer` security scheme; explicit `operation_id` on every route; auth extracted into `require_api_key` Depends; duplicate cost route removed; `GET /api/v0/version` | Implemented |
| 74 | Automation substrate — `ze-automation` core package owns full automation stack (types, stores, planners, executors, agents, migrations); `ze-personal` reduced to persona + contacts + onboarding | Implemented |
| 76 | ze-api shell cleanup — domain bootstrap into package modules; `ZeApiSettings` shell; test relocation; delete `ze_api/bootstrap.py`; `compose.py` for proactive jobs | Implemented |
| 77 | ze-logging — structlog configuration extracted from ze-api/ze-agents into `core/kernel/ze-logging`; `get_logger` via ze-sdk | Implemented |
| 78 | Dream Memory — sleep pass (78a) + dream synthesis, NLI gates, two-critic pipeline, promoter, REST API (78b) | Implemented |
| 79 | NLI cross-encoder — contradiction detection, retrieval re-rank cache, correlation grounding (`ze_core/nli.py`) | Implemented |
| 80 | NLI Client + plugin access — `NLIClient` Protocol, DI, shared `@tool`s | Implemented |
| 81 | Plugin NLI adoption — news dedup, finance merchant merging | Implemented |
| 83 | ze-communication + ze-messenger — channel contract extracted to `core/contracts/ze-communication`; `GmailChannel` moved to `ze-google` as `InboundChannel`; `ze-email` renamed to `ze-messenger` | Implemented |
| 85 | Messaging Hub — `channel_id` identity, `UserChannelStore`/`ChannelWatermarkStore`/`ThreadChannelMap` (ze-personal), `InboundPollingJob`, `InboundMessageProcessor`, `MessagingSignalSource` (ze-messenger), thread-aware `send_email`, `ChannelRegistry` on container, `GET/PATCH /api/v0/channels` | Implemented |
| 88 | Memory Feed — reverse-chronological paginated stream of facts + episodes; `GET /api/v0/memory/feed` with cursor pagination + type/agent filters; `/brain/memory` React page with infinite scroll + inline fact review | Implemented |
| 89 | Message Trace — per-message explainability; `trace` JSONB column on `messages`; `record_trace` graph node; `GET /api/v0/messages/{id}/trace`; collapsible "Why?" panel in chat UI | Implemented |
| 90 | Ze's Mind Split-Pane — real-time context sidebar in chat; `trace_update` WS frame emitted post-graph; 320 px resizable right panel showing routing/memory/tools for latest message | Implemented |
| 91 | Goal Dashboard v2 — `GET /api/v0/goals/{id}` detail + `GET /api/v0/goals/{id}/traces`; milestone timeline, gate status, execution trace log, learnings sidebar at `/goals/:goalId` | Implemented |
| 92 | Agent Activity Heatmap — calendar heatmap of agent usage by day; `GET /api/v0/activity/heatmap` aggregates `messages.trace`; section on Usage (`/costs`) using `@uiw/react-heat-map` | Implemented |
| 93 | Temporal Memory Timeline — `as_of` param on `GET /api/v0/memory/feed`; `GET /api/v0/memory/timeline-bounds`; date scrubber on Memory Feed page for time-travel memory view | Implemented |
| 94 | Memory Graph View — interactive entity/relationship graph; `GET /api/v0/memory/graph` + entity detail endpoint; `/brain/graph` page using React Flow + dagre layout; click-to-expand neighbourhoods | Implemented |
| 95 | Unified Streaming Architecture — switch `invoke_raw_turn` (now in `ze_core/conversation/turn.py`) to `astream_events`; emit partial `trace_update` frames as graph nodes complete (routing → memory → tools → final); token streaming for messages already works; trace panel fills progressively | Implemented |
| 102 | Workflow Conditional Branching — stable step ids, per-step `branches` (condition → target) and `default_next`, falling back to sequential order | Implemented |
| 103 | Model Default with Overrides — `models.default` + `models.overrides` in `config.yaml`; resolution order override → agent's declared model → default | Implemented |
| 104 | Workflow Flowchart View — replace the flat timeline run view with a top-to-bottom flowchart (`@xyflow/react` + `dagre`); steps as nodes, `branches`/`default_next` as labeled edges, executed path highlighted via `branch_taken`; full replacement of `WorkflowStepsList` | Implemented |
| 105 | Notification Center — `notifications` table owned by `ze-proactive` (`zpro002`); `ProactiveNotifier.notify()` structured path; `GET/POST /api/v0/notifications` REST surface; live `notification` WS frame; `entities/notification` + `widgets/notification-bell` replacing the decorative Bell in `TopBar` | Implemented |
| 106 | Memory Retrieval Relevance — real cosine similarity + configurable relevance floor across all `ze-memory` policies; entity-anchored retrieval (`entity_anchor.py`, one-hop `GraphStore.expand()` from query-text entity matches); composite ranking (`composite.py`, similarity × recency decay × confidence) before token budgeting; synchronous live NLI rerank (`retrieval_rerank.live_rerank`) distinct from the async session cache; Mind panel shows real relevance, not extraction confidence | Implemented |
| 107 | Workflow Resilience and Control — per-step `on_failure` policy (`fail` / `continue` / `skip_to:<step_id>`, no separate critical flag), retries for transient step failures, partial-result synthesis when a step fails the run | Implemented |
| 108 | Workflow Revision Audit — append-only `workflow_revisions` log (`zc026`) on every workflow create/step-edit (agent tool + REST), before/after steps, human-readable diff summary, actor context (agent session/message id or API); `GET /api/v0/workflows/{id}/revisions`; "Change History" section on workflow detail page with "View conversation" deep link and a link from the 107b definition-changed banner | Implemented |
| 109 | Open-Loop Substrate — new core `ze-worldstate` package: `OpenLoop` (`suspected`→`active`→`drifting`→`closed`\|`dropped`), honest provenance, continuous confidence with evidence-linked decay cascade, entity-overlap/embedding dedup, stale-suspicion expiry job; loops reuse `ze-memory`'s `memory_relationships`/`GraphStore` (new `open_loop` bucket) rather than a parallel model; wired into all four inflows (conversation, email, calendar, ingestion); `GET/POST /api/v0/loops` REST surface; `widgets/loop-review` | Implemented |
| 110 | Open-Loop Drift Detection & Surfacing (Phase B) — `drift_deadline`/`drift_rationale` columns (`zw002`), scheduled `DriftSweepJob` + immediate contradiction path (`decay.py`) moving `active`→`drifting`; `ze_core` `surface_loops` node (entity-overlap inline mentions, no gating); `ze-worldstate → ze-correlation` dependency reusing extracted push-bar functions (`ze_correlation/push.py`) via `LoopSurfacer.passes_push_bar` + `PushSweepJob`, sibling `push_log` budget and inline-then-push cooldown | Implemented |
| 111 | Claim Topology — shared `ClaimKind`/`Provenance`/`Confidence`/`decay()` vocabulary in `core/contracts/ze-agents/ze_agents/claims.py`; fixes frozen `Hypothesis.confidence` via new `HypothesisDecayJob` (`zcor002`); retrofits `OpenLoop`, `memory_facts` (`zm016`), and `Signal` (`zm017`) onto the shared vocabulary, `OpenLoop.provenance` unvalidated against a closed core whitelist; extracts `is_stale()` staleness helper into `core/contracts/ze-proactive`, shared by `StaleSuspicionJob`/`DriftSweepJob`/`PostgresGoalStore.list_stuck` | Implemented |
| 112 | Session Context Continuity — replaces `write_memory`'s blind `[-SESSION_HISTORY_LIMIT:]` trim with a 70%-of-context-window compaction check (`ze_core/openrouter/context_windows.py`, LLM-produced rolling summary folded ahead of the verbatim tail, graceful fallback to the old trim on LLM failure); replaces `fetch_context`'s blank-history-on-gap side effect with a silent resume recap (`ResumeRecap`, session narrative + open loops + in-flight goals/workflows) injected into the system prompt via `AgentContext.resume_recap`, never appended to `messages`; both recorded on `MessageTrace` (`compaction`, `resume_recap_applied`) for trace-panel inspectability; no new graph nodes, no new tables | Implemented |
| 113 | Proactive/Concurrency Hardening Sweep — three independent reliability fixes: `pending_confirmations` + in-process `pending_configs` rekeyed from `thread_id` to `request_id` (`zc027`) so concurrent confirmation gates on one thread can't clobber or cross-cancel each other; opt-in `budget:` config block + `SpendBudgetChecker`/`ze_core/telemetry/pricing.py` composed into `capability_check` (strictest-wins with `CapabilityGate`), holding execution via the existing `AWAIT_CONFIRMATION` gate when session/day spend would exceed a configured ceiling; `push_log` idempotency key + unique index (`zpro003`) turns `LoopSurfacer.log_push`/`PushSweepJob` from notify-then-log into claim-then-notify (`claim_push`/`release_push_claim`), closing the concurrent-sweep double-notify race and rolling back the claim on notifier failure | Implemented |
| 114 | Agent Skills — new core `ze-skills` package: import `SKILL.md` from a URL or zip, pending-review gate before any conversation effect, embedding-similarity + `/skill-name` matching applied globally across agents, `allowed-tools` intersects (never unions) an agent's tools, usage on `MessageTrace.skills_used`/`trace_update`; bundled skills via `ZePlugin.bundled_skill_paths()`; daily `SkillRecheckJob` reverts to pending review on source content change; `GET/POST /api/v0/skills` + `widgets/skill-management` | Implemented |
| 115 | Workspace Environment — durable isolated computer beside Ze (`core/ops/ze-workspace` + `sidecar/workspace`); chat-first (no execution modes; `/workspace` is a map); in-turn files and commands; skill scripts after a second executable approval (`zsk002`). `ze-core`/`ze-agents` must not import `ze_workspace`. Detach/follow-up/push is spec 116. | Implemented |
| 116 | Workspace Follow-Through — wait-then-detach workspace runs, automatic follow-up turn on the same thread, push when offline, cancel; one-run-at-a-time busy rule delivered by Phase 129 (`_refusal_if_busy`) | Implemented |
| 117 | Web HIG fixes — chat always resolves (delivery watchdog + retry state in ze-web; backend keeps the socket on unserializable frames, JSON-safe `trace_update`, terminal `error` frame for empty turns, `thread_id` on error frames), md-width nav flyout + accessible names, route-derived contextual panel label, mobile launcher/nav polish, static AI disclosure; feedback/retry split to a later phase | Implemented |
| 118 | Chart Visualization — `@myguyze/ze-ui` chart primitives + server-driven UI descriptors so agents can render a real chart (not a text table) directly in chat responses | Implemented |
| 119 | Memory Graph Charts — per-entity activity charts on the `/brain/graph` entity detail panel | Implemented |
| 120 | Usage Dashboard Charts — real spend-trend chart on the Costs/Usage page, replacing static summary numbers | Implemented |
| 121 | Memory Feed Charts — memory-growth-over-time chart on `/brain/memory` | Implemented |
| 122 | Data Overview Charts — storage-composition chart replacing `StorageDonutChart` on the data overview widget | Implemented |
| 123 | Attention Arbitration — `PriorityView` ranks drifting loops, stuck goals, and hypotheses on one scale; shared push budget across proactive sources | Implemented |
| 124 | Contribution Seam Core — typed `Contribution` proposals with `validate_and_submit`; reflection migrated onto the seam | Implemented |
| 125 | Contribution Seam Extension — social cognition (contacts/relationships) and action producers onto the seam | Implemented |
| 126 | Contribution Collision Detection — `ze-collision` package, `contribution_collisions` log (`zcol001`), `submit_and_detect_collisions` | Implemented |
| 127 | User-Directed Priority Override — `PriorityOverride` (`ze-priority`'s first store, `zpri` migration chain), snapshot view + drag reorder + conversational `reprioritize_item` tool, decaying/pinned overrides merged into `PriorityView.rank()` at render time, `ze_collision` skip rule narrowed to `(source_function, provenance)` so user-vs-executive priority disagreement is observable | Implemented |
| 128 | Social Cognition Foundation — `project` entity and `WORKS_ON` / `COLLABORATES_WITH` edges in the memory graph, decaying `last_contact`, stale follow-up nudges in the shared push budget | Implemented |
| 129 | Workspace Run Journal — run handles the mind can reattach to after restart (`zws003`), watch stream, busy refusal | Implemented |
| 130 | Social Cognition Co-Occurrence — project-person co-occurrence inference (`ze_personal/social/`, `SOURCE_WEIGHTS`, 30-day window) as correlation hypotheses, promoted to identity on corroboration | Implemented |
| 131 | Workspace Live Output — live output of a detached workspace run shown to the user in chat | Implemented |
| 132 | Priority Turn Surfacing — conversation inline mentions, resume recap, and explicit what's-open consume merged `PriorityView` (including Phase 127 pins) via `TurnSurfacing` injected as `config["configurable"]["turn_surfacer"]`; relevance still gates unsolicited mentions; component type `open_items`; no store merge, no push-budget change | Implemented |
| 133 | Perception Facts onto the Contribution Seam — conversation, ingestion, inbound-message, and onboarding facts submitted as `PERCEPTION` / `FACT` contributions | Implemented |
| 134 | Memory Facts Hard-Cut — `memory_facts` onto the shared claim vocabulary; public `propose_facts` removed | Implemented |
| 135 | Action Record Ledger — append-only `ActionRecord` ledger (`action_records`, `zm021`) | Implemented |
| 136 | Action Instrumentation — workspace, messaging, calendar/reminders, goal/workflow, and prospecting producers each submit an `ActionRecord` citing their domain record | Implemented |
| 137 | Evidence-Backed Goal Learning — one evidence-bearing `GoalLearning` model (`zc030`) replaces `goal_learnings` and the `goals.learnings` blob | Implemented |
| 138 | Governed Procedure Lifecycle — procedure candidates, admissions, versions, and lifecycle events (`zm022`) replace direct writes to `memory_procedures` | Implemented |
| 139 | Governed Procedure Activation — validated procedures discoverable and explicitly invocable (`invoke_procedure`), never granting tools; invocations and feedback recorded (`zm023`) | Implemented |
| 140 | Memory admission + remember/forget — keep/drop extractor with closed families; companion `remember_fact`/`forget_fact` through the contribution seam; `AgentResult.memory_proposals` removed | Implemented |
| 141 | Memory read contract + prompt constitution — reviewed facts always-on; `_format_memory` origin/confidence/recency; constitution + job before biography; silent fact use; `TurnSurfacing` stays for open items | Implemented |
| 142 | Speech-act routing — extractor `speech_act` gate; companion routes timed remember to reminders, lingering concerns to loops, multi-week outcomes to goals | Implemented |
| 143 | Earned memory confirmations and precise forget | Implemented |
| 144 | Constraint veto on gated writes | Implemented |
| 145 | Unsolicited recitation reply gate | Implemented |
| 146 | Forget vs cancel across stores | Implemented |
| 147 | Ingest vs remember honesty | Implemented |
| 148 | Extractor dual-write identity skip | Implemented |
| 149 | Specialist memory constitution (calendar, messenger, news) | Implemented |
| 150 | Eval `memory_proposals_count` hard-cut and guide phase-index honesty | Implemented |
| 151 | Fat delegate ACI | Implemented |
| 152 | Per-delegate capability and confirmation | Implemented |
| 153 | Sequential routing hard-cut | Implemented |
| 154 | Conductor observability and eval | Implemented |
| 155 | Mixed gather+act → conductor | Implemented |
| 156 | Conductor stall / replan | Implemented |
| 157 | Promote conductor instance to workflow/goal | Implemented |
| 158 | Parallel per-subtask gates (independent fan-out) | Implemented |
| 159 | Concurrent thread identity (99 remainder: per-thread trace/cancel; 4000 stays) | Implemented |
| 160 | E5 routing confidence (97 remainder: retune MiniLM-era threshold/gap; docs name E5) | Implemented |
| 161 | Workspace chat-first (drop execution modes; `/workspace` is a map; unattended always has the computer) | Implemented |
| 162 | System One client — `SystemOneClient` Protocol (`ze_agents/system_one.py`) for typed judgments (noul / choice / score); `OpenRouterSystemOneClient` + `DisabledSystemOneClient` in `ze_core/openrouter/system_one.py`; `system_one:` config block, off by default; no routing or admission change yet | Implemented |
| 163 | Speech-act System One — post-turn fact admission judged by System One (`speech_act`/family Choice + biography Noul), pure-code persist/hold/skip, Haiku value writer on persist, Haiku judge on skip, single attempt (`evaluate(max_attempts=1)`), judgments on the trace; on in the shipped config with bars calibrated 2026-10-09 (`make calibrate-speech-act`) | Implemented |
| 164 | Routing Choice After E5 — E5 stays the shortlist; a typed System One Choice decides single-specialist trust and a graded complexity question replaces the word-count classifier (depends on 162); shipped off (the 2026-10-09 calibration found no safe `choice_trust`); enabled by phase 167 | Implemented |
| 165 | Response Feedback and Retry — thumbs up/down on assistant replies as append-only `FeedbackRecord` evidence (`ClaimKind.FEEDBACK_RECORD`, licensed to Perception only; `feedback_records`, `zm024`), linked to the reply's `MessageTrace`, no consumer in v1; safe Retry regenerates the latest reply with write tools blocked (`retry_mode`), decided server-side by `retry_eligibility` from trace effect metadata; `messages.replaces`/`replaced_by` (`zc031`); every `WRITE` tool declares `reversibility` | Implemented |
| 166 | System One Skill Gating (O3) — E5 shortlists skills down to `shortlist_floor`; one batched System One Choice (shortlist ∪ `none`) plus a Noul `needs_skill` picks at most one automatic skill (a deliberate narrowing of 114; explicit `/skill-name` still stacks); a below-`match_threshold` apply is marked `below_floor` on the trace; `match_skills` appends its judgments; surface `system_one.surfaces.skills` shipped off with null bars until `make calibrate-skills`, then enabled 2026-10-12 with `choice_trust` 0.75, `needs_skill_hold` 0.6, `shortlist_k` 5; no suggestion UX | Implemented |
| 167 | Routing Choice Criteria — fixes the 164 held-out failures: companion no longer claims "explain X"; optional `routing_criteria` on `BaseAgent` (Choice text, falls back to `description`; E5 still embeds `description`); name-free Choice instructions and a stronger `none` criterion; `shortlist_k` 9 chosen by offline recall on three calibration sets (9 of 10 agents, so E5 filters little for the Choice; it still drives the 160 skip path); `eval/calibration/routing_holdout2.jsonl` and the opt-in `companion_research_check.py`. Surface enabled (`choice_trust` 0.5, `multi_specialist_hold` 0.5, `complexity_lookup_max` null) under an amended acceptance rule | Implemented |
| 168 | Loop Extraction Gate (O4) — one batched System One request asks three Nouls (`is_open_concern`, `resolves_existing`, `explicit_declaration` on conversation only); pure `decide()` in `ze_worldstate/loop_judge.py` maps them to resolve / create-declared / create-suspected / hold; Haiku only writes the title (and optional `implied_window_days`) after a positive gate; `LoopInflow` (`admission.py`) owns gate and commit; conversation gate runs in `write_memory` beside the fact extractor (rows on `MessageTrace.judgments`, fire-and-forget commit), worldstate `conversation_memory_hook` deleted; email/calendar/ingestion run the gate, log judgments, and write no trace rows; off, uncalibrated, skip or invalid → the 109 Haiku gate; surface `system_one.surfaces.loop_gate` enabled 2026-10-12 (`loop_hold` 0.75, `explicit_hold` 0.85, `resolves_hold` 0.8) after an `ENABLE` verdict for EN and PT on the held-out set; the 109 Haiku fallback fails to parse Haiku's fenced JSON, so before 168 production created no loops; no migration | Implemented |

## graphify

Full-repo knowledge graph lives at `graphify-out/` (`graph.json`, `GRAPH_REPORT.md`,
`graph.html`). Keep the corpus at repo root — do not rebuild on a subfolder unless
explicitly asked. AST extraction is free; semantic extraction only covers docs/specs.

**What it is:** an import/call graph with community detection — not a reasoning layer.
It will not invent DI wiring, shared SQL tables, or “why this design exists.” Prefer
specs/`AGENTS.md` for architecture intent.

**When to use it (prefer in this order):**
1. `graphify affected "<ExactSymbol>" --depth 2` — reverse traversal: everything that
   imports/calls/uses the symbol (blast radius of a change)
2. `graphify explain "<ExactSymbol>"` — who imports/calls a known type or function
3. `graphify path "<A>" "<B>"` — shortest structural path between two exact symbols
4. `graphify-out/GRAPH_REPORT.md` / `graphify god-nodes` — hubs, import cycles (broad scan)
5. `graphify query "<question>" --budget 800` — only with concrete symbol/file names;
   raise `--budget` if truncated. Broad NL queries on this monorepo are noisy.

**When not to lead with graphify:** open-ended “how does X work?”, “why?”, or
behavior that isn’t an import/call edge (SQL predicates, YAML config, WS frame
shapes). Use Grep / Read / specs instead, then optionally confirm with `explain`.

**In the multi-agent workflow (Maestri floors):**
- *Spec Architect* — run `affected` on every symbol a phase changes and put the
  blast radius (callers by package) in the scope write-up and plan.
- *Engineers* — run `affected` before changing a signature, Protocol, or shared type,
  and update every caller in the same change.
- *Reviewers* — run `affected` on each changed public symbol to find callers the diff
  did not touch, and `path "<plugin module>" "ze_core"` (or any forbidden pair from the
  dependency graph) to catch boundary violations an import grep misses.
- *Docs Steward* — use `god-nodes` and `GRAPH_REPORT.md` to check architecture docs
  name the real hubs and package edges.
- After a query that helped or misled, record it, always with `--memory-dir` pointing
  at the ground checkout (a floor's own `graphify-out/memory/` is deleted when the floor
  lands, so outcomes saved there are lost):
  `graphify save-result --question "…" --answer "…" --type query --outcome useful|dead_end|corrected --memory-dir /Users/joaoamatos/coding/ze/graphify-out/memory`.
  The weekly docs sweep runs `graphify reflect --memory-dir /Users/joaoamatos/coding/ze/graphify-out/memory`
  to turn these into lessons.

**Keep it fresh:** `graphify update .` is AST-only, free, and takes about a minute.
The Maestro runs it on the ground checkout after every landed floor, so new floors
start from a current graph. On a floor, run it in your checkout before structural
queries once your own changes matter. Do not run it on every commit. Full rebuild only
when the graph is missing or badly stale. `graphify-out/` is gitignored — local/cache only.
OpenCode agents get a one-line reminder from `.opencode/plugins/graphify.js`.

When the user types `/graphify`, follow the graphify skill before other exploration.

## Documentation style

Public-facing docs (root READMEs, `VISION.md`, `CONTRIBUTING.md`, `SECURITY.md`,
`docs/*.md`) follow Orwell's six rules plus an ASD-STE100-inspired plain-English
discipline — active voice, short sentences, no needless words, American spelling.
Does not apply to `specs/`, `CLAUDE.md`, or `AGENTS.md`. See the `doc-style` skill
(`.claude/skills/doc-style/SKILL.md`) before drafting or editing these files.

### Diagrams in docs

When drafting or editing `docs/*.md`, ask whether a reader would learn more from
a visual than from prose — architecture, request/data flow, state machines,
sequence interactions, layered systems, timelines. If yes, use the `diagram-design`
skill (`.claude/skills/diagram-design/SKILL.md`) to produce a branded SVG/HTML
diagram instead of hand-rolled ASCII box-drawing art. Don't diagram what a short
paragraph already says clearly — see the skill's own density guidance (§1–2)
before adding one.

## Learned User Preferences

- Write a spec before significant new features: `/speckit-specify` for `specs/phases/` features, or an ADR in `specs/arch/` (follow the existing ones) for cross-cutting decisions.
- Until v1, break APIs and schemas when the design is wrong. Do not add compatibility shims, dual-write, or wrap-then-replace across phases (`specs/arch/pre-v1-hard-cuts.md`, constitution Principle VIII).
- When implementing from an attached Cursor plan or a speckit phase: do not edit `plan.md`; use the pre-created todos. Check off speckit `tasks.md` via companion `write-context.py --append` then `--materialize` (never hand-edit checkboxes); run the speckit after-implement hook when implementation finishes.
- Ze's user-facing interface is the React web app (`ze-web`), not Telegram — do not describe Telegram-style UI capabilities to users.
- Only create git commits when explicitly asked. When asked to commit a large batch, split by logical phase or spec user story rather than one dump.
- Chat chrome: the generic side panel is **trace** (not "Ze's Mind"); session history lives there too. Do not duplicate page titles already shown in the top bar.
- Discuss and pin spec scope before creating speckit files unless explicitly asked to write them.
- Implement multi-phase roadmaps in order: finish tests and mark the current spec Implemented before starting the next.
- Workspace is chat-first: interact via chat; `/workspace` is a high-level map (tree/info only), not a run console; do not bring back execution modes; unattended always has the computer.
- After a multi-spec batch is Ready to implement, leave a copy-paste handoff/goal prompt for the next session.

## Learned Workspace Facts

- `core/ops/ze-seed` (Phase 96) seeds dev data when `AUTO_SEED_DEV_DATA=true` (default on `make dev` / `make dev-full`); each run wipes the `seed-dev-*` namespace and re-applies narrative fixtures; plugins extend via `ZePlugin.seed_domains()`.
- `ze-email` was renamed to `ze-messenger` (`plugins/ze-messenger/`); Gmail inbound channel lives in `integrations/ze-google`.
- Plugin management UI registers via `ZePlugin.ui_contributions()`; `ze-web` loads nav/settings from `GET /api/v0/ui/manifest`; plugin REST routes mount via `rest_routes()`.
- `apps/ze-web` follows Feature-Sliced Design: `pages → widgets → features → entities → shared`; query hooks live in `entities/<name>/api/`.
- Chat inline UI uses `ze-components` `render_*` tools (table, metric, list, timeline, progress, confirm, form) rendered by `PrimitiveRenderer` below message bubbles.
- `journal/` and `brag-output/` are gitignored local writing; treat as authoring notes, not product source.
- Web nav groups: Knowledge (memory, graph, procedures); Automation (goals, workflows, priority, skills — Bot icon); System (usage, data, workspace).
- Keep the phase 115 workspace sidecar (`core/ops/ze-workspace` + `sidecar/workspace`); chat-first map at `/workspace`; do not replace with Cloudflare Computer — borrow run-handle / exec-journal ideas instead.
- Perception/memory fact writes go through the contribution seam (`specs/arch/contribution-seam.md`): Phase 133 wraps writers; Phase 134 hard-cuts `memory_facts` onto shared claim vocabulary and removes public `propose_facts`.
- Experiential learning is phases 135–139 (action-record ledger, instrumentation, evidence-backed learning, procedure lifecycle/activation); procedures are first-class, not only goal/workflow steps.
- Memory honesty is phases 140–150 in `specs/arch/memory-honesty-roadmap.md`. Companion-conductor is `specs/arch/companion-conductor-roadmap.md` (151–161): companion sole speaker/conductor, fat `delegate_to_agent`, no `plan_sequential`/swarm; phase dir 151 is conductor ACI, not memory-honesty.
- Every `WRITE` `@tool` declares `reversibility` (plus `undo_tool`/`undo_note` when reversible, and `effect_phrase`); an undeclared WRITE tool fails registration. Retry eligibility reads it. Perception holds two licences: `FACT` and `FEEDBACK_RECORD`.
- `.cursor/rules/` is gitignored; do not commit Cursor rules.
