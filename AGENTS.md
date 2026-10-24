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
│   │   │       ├── base_agent.py # BaseAgent ABC with agentic_loop; optional routing_criteria (Choice text, falls back to description)
│   │   │       ├── claims.py    # Shared ClaimKind / Provenance / Confidence / decay() vocabulary
│   │   │       ├── client.py    # LLMClient Protocol
│   │   │       ├── db.py        # DBPool Protocol
│   │   │       ├── delegate.py  # delegate_to_agent — conductor fan-out to specialists
│   │   │       ├── errors.py    # Full ZeError hierarchy
│   │   │       ├── rollback.py  # RollbackScope ContextVar, is_error_result — undo plumbing for Retry
│   │   │       ├── hooks.py     # HarnessHook ABC (agentic loop — not a plugin concern)
│   │   │       ├── llm_json.py  # parse_llm_json — tolerant JSON parse of LLM replies (fences, prose), raises LLMJsonParseError
│   │   │       ├── registry.py  # @agent decorator + module-level agent registry
│   │   │       ├── settings.py  # Settings dataclass
│   │   │       ├── screen.py    # ScreenContext/ScreenRef wire types (from_wire never raises), ScreenResolver protocol, sanitize_text
│   │   │       ├── system_one.py # SystemOneClient Protocol — typed judgments (noul / choice / score)
│   │   │       ├── park.py      # Parked writes, loops and subtasks; WriteConfirmation
│   │   │       ├── effects.py   # effect_imperative, ensure_declined_lines
│   │   │       ├── scripts.py   # run_tool_script contract: ScriptLimits, ScriptRunner Protocol, budget ContextVars
│   │   │       ├── script_stub.py # ze_tools stub builder, normalize_source, tool_signature (pure)
│   │   │       ├── script_step.py # run_script_step — dispatcher, result shaping, proposed writes
│   │   │       └── tool.py      # @tool decorator, ToolAccess, asks_first, produces_ui, egress
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
│   │   └── ze-proactive/        # Job scheduling + interruption governor (classes, quiet hours, catch-up)
│   │       └── ze_proactive/    # ProactiveJob, ProactiveScheduler, ProactiveNotifier (notify/governor), PushKind, PushLogStore
│   ├── engine/                 # The orchestration engine itself
│   │   └── ze-core/             # Engine — routing, orchestration, telemetry, DI container
│   │       └── ze_core/
│   │           ├── conversation/# invoke_raw_turn (turn.py) — streamed graph turn entry point; retry.py (Retry eligibility), rewind.py, rollback.py (run_rollback — undo a reply's actions before a retry)
│   │           ├── openrouter/  # OpenRouterClient, System One client (engine internal — plugins use the Protocols)
│   │           ├── orchestration/# graph_builder, graph nodes, AgentState, edges, judgment_state (shared System One state), timing.py (timed() wraps every node)
│   │           ├── screen/      # Screen resolver registry + build_screen_note (the 1,200-character screen note built before routing)
│   │           ├── routing/     # EmbeddingRouter, tier.py (System One model tier), fallback, store
│   │           ├── telemetry/   # CostTracker, CostReconciler, PostgresCostStore, ContextVar, turn.py (TurnTelemetry per-turn recorder)
│   │           ├── container.py # Base Container with DI wiring and invoke/resume entry points
│   │           ├── voice.py     # transcribe_audio — measure, limit and transcribe one voice recording (route)
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
│   │   ├── ze-memory/            # Memory — facts, episodes, graph, retrieval, fact_judge.py (System One fact questions), feedback_records/ (reply feedback evidence)
│   │   ├── ze-correlation/       # Cross-domain hypothesis formation
│   │   └── ze-worldstate/        # Open-loop substrate — active concerns, honest provenance, evidence-linked confidence
│   │       └── ze_worldstate/
│   │           ├── types.py     # OpenLoop, LoopState, LoopClaimKind, LoopProvenance
│   │           ├── store.py     # LoopStore Protocol + PostgresLoopStore
│   │           ├── matching.py  # entity-overlap + embedding-similarity dedup
│   │           ├── decay.py     # confidence decay cascade, called at the evidence-writing code path
│   │           ├── extraction.py # conservative relevance-gated loop extraction (109 Haiku gate = fallback)
│   │           ├── commitment_judge.py # System One commitment intake — Choice + fact/loop Nouls, six bars, pure decide()
│   │           ├── intake.py    # CommitmentIntake — one request per conversation turn: facts, loop commit, reminder/goal links
│   │           ├── loop_judge.py # System One loop gate for email/calendar/ingestion — two Nouls, bars, pure decide()
│   │           ├── admission.py  # LoopInflow — gate + Haiku title writer + commit
│   │           ├── corroboration.py # independence rule + confidence arithmetic + corroborate/promote effects
│   │           ├── corroboration_judge.py # System One same_concern Noul — state, bars, pure decide()
│   │           ├── tracking.py   # LoopTracker — user-asked loop (track_loop tool): normalize, match, create/confirm/reinforce/revive
│   │           ├── review.py    # confirm/close/drop lifecycle transitions
│   │           ├── inflow.py    # inflow wiring helpers (messenger/calendar/ingestion extractors)
│   │           ├── jobs/        # stale-suspicion expiry job
│   │           └── migrations/  # zw001 (open_loops), zw002 (drift columns), zw003 (open_loop_sources), zw004 (reminder_id), zw005 (confidence_prior)
│   ├── automation/              # Goals, workflows, skills — built on cognition
│   │   ├── ze-automation/        # Core automation engine — goals, workflows, accountability, planners, executors, agents
│   │   │   └── ze_automation/
│   │   │       ├── goals/       # GoalStore, GoalPlanner, GoalExecutor, PostgresGoalStore, GoalSuggestionStore, types
│   │   │       ├── workflow/    # WorkflowStore, WorkflowPlanner, WorkflowScheduler, PostgresWorkflowStore, types
│   │   │       ├── accountability/ # AccountabilityStore, ActivitySummary, AnomalyRecord, build_narrative
│   │   │       ├── agents/      # GoalAgent, WorkflowManagerAgent
│   │   │       ├── holds/       # plan-time approved writes for unattended runs (phase 181)
│   │   │       ├── jobs/        # goal/workflow/accountability proactive jobs
│   │   │       ├── runtime/     # AutomationPlanner, AutomationStore contracts
│   │   │       └── migrations/  # zc006–zc009 (goal traces/suggestions/stuck/reuse), zc011 (workflows), zc014 (accountability),
│   │   │                        # zc021/zc025 (workflow execution summary/snapshot), zc026 (workflow revisions), zc030 (goal learning claims), zc031 (message supersession), zc032 (messages.rollback)
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
│   │       └── ze_priority/compose/ # WorldComposer — composed answers (slipping, decisions, topic) + show_* companion tools
│   └── ops/                     # Environment, onboarding, ingestion, seed data, eval
│       ├── ze-workspace/         # Isolated computer — files, shell, skill scripts
│       │   └── ze_workspace/
│       │       ├── client.py    # WorkspaceClient HTTP to sidecar
│       │       ├── scripts.py   # WorkspaceScriptRunner — WS /scripts relay for run_tool_script
│       │       ├── script_learning.py # tool_script procedure candidates from script action records
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
│   │   │   ├── wiring/       # container.py (ZeContainer, registers all ZePlugins), jobs.py (proactive job registration), hooks, stores, agents
│   │   │   ├── cli/          # migrate.py (meta-runner: discovers all package migration paths), seed.py, openapi_export.py
│   │   │   └── settings.py   # ZeApiSettings (shell env + YAML)
│   │   ├── config/
│   │   │   ├── config.yaml   # Models, contacts, proactive schedules (secrets in .env)
│   │   │   └── persona.yaml  # Persona profiles and dials
│   │   └── tests/
│   └── ze-web/               # React web client (Vite + TypeScript + Tailwind + shadcn/ui)
├── sidecar/                  # Docker sidecars: browser/ (Playwright), workspace/ (isolated computer)
├── eval/                     # Eval test data and entrypoints (uses core/ops/ze-eval)
│   ├── scenarios/            # YAML scenario definitions — edit these to add tests
│   ├── calibration/          # System One calibration sets + runner (make calibrate-commitment-intake)
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
ze-components   → ze-agents, ze-logging  core/kernel/
ze-agents       → ze-logging  core/contracts/
ze-communication→ ze-agents                core/contracts/  ← channel types, ABCs, registry
ze-plugin       → ze-agents, ze-communication, ze-data, ze-logging  core/contracts/
ze-proactive    → ze-agents, ze-data, ze-logging  core/contracts/
ze-core         → ze-agents, ze-communication, ze-components, ze-data, ze-logging, ze-memory, ze-plugin  core/engine/  ← engine; never a plugin dep
ze-collision    → ze-agents, ze-logging, ze-plugin  core/seam/  ← contribution collision detection; wired by ze-api directly
ze-memory       → ze-agents, ze-collision, ze-data, ze-logging, ze-plugin, ze-proactive  core/cognition/  ← ze-plugin: Contribution seam (Signal write path)
ze-correlation  → ze-agents, ze-collision, ze-logging, ze-memory, ze-plugin, ze-proactive  core/cognition/  ← cross-domain hypothesis formation; ze-plugin: Contribution seam
ze-worldstate   → ze-agents, ze-collision, ze-correlation, ze-data, ze-logging, ze-memory, ze-plugin, ze-proactive  core/cognition/  ← open loops; wired by ze-api directly; ze-plugin: Contribution seam (loop write path)
ze-automation   → ze-agents, ze-components, ze-data, ze-logging, ze-memory, ze-plugin, ze-proactive  core/automation/  ← goals + workflows; wired by ze-api directly
ze-skills       → ze-agents, ze-logging, ze-memory, ze-plugin, ze-proactive  core/automation/  ← agent skills; wired by ze-api directly
ze-priority     → ze-agents, ze-automation, ze-collision, ze-components, ze-correlation, ze-logging, ze-plugin, ze-worldstate  core/arbitration/  ← attention arbitration (PriorityView + shared push budget) + user-directed priority override; wired by ze-api directly; ze-plugin: Contribution seam (reprioritization write path)
ze-workspace    → ze-agents, ze-logging, ze-memory, ze-plugin, ze-proactive  core/ops/  ← isolated computer; wired by ze-api; ze-core/ze-agents must not import it
ze-onboarding   → ze-agents, ze-memory, ze-plugin  core/ops/
ze-ingestion    → ze-agents, ze-browser, ze-logging, ze-memory, ze-plugin  core/ops/  ← imports ze_yt optionally (try/except ImportError)
ze-seed         → ze-core, ze-logging  core/ops/
ze-eval           (no ze deps — HTTP only) core/ops/  ← eval infrastructure
ze-sdk          → ze-agents, ze-automation, ze-collision, ze-communication, ze-correlation, ze-data, ze-logging, ze-memory, ze-onboarding, ze-plugin, ze-proactive  packages/  ← plugin entry point
ze-browser      → ze-agents  integrations/
ze-notifications  (no ze deps)             integrations/
ze-trading212     (no ze deps)             integrations/
ze-google       → ze-agents, ze-communication  integrations/  ← GmailChannel lives here
ze-yt           → ze-ingestion, ze-logging  integrations/
ze-personal     → ze-automation, ze-components, ze-news, ze-priority, ze-sdk, ze-seed  plugins/
ze-messenger    → ze-google, ze-personal, ze-sdk  plugins/
ze-prospecting  → ze-browser, ze-personal, ze-sdk  plugins/
ze-calendar     → ze-components, ze-google, ze-personal, ze-sdk, ze-seed  plugins/
ze-news         → ze-components, ze-sdk  plugins/
ze-finance      → ze-ingestion, ze-sdk, ze-trading212  plugins/
ze-api          → ze-agents, ze-automation, ze-browser, ze-calendar, ze-collision, ze-communication, ze-components, ze-core,
                    ze-correlation, ze-data, ze-finance, ze-google, ze-ingestion, ze-logging, ze-memory, ze-messenger, ze-news,
                    ze-notifications, ze-onboarding, ze-personal, ze-plugin, ze-priority, ze-proactive, ze-prospecting, ze-seed,
                    ze-skills, ze-workspace, ze-worldstate, ze-yt   apps/
ze-web            (React — connects to ze-api over WebSocket, no Python deps)         apps/
```

No known drift from the import rules below. `packages/ze-sdk/tests/test_plugin_boundaries.py`
fails when plugin code imports `ze_core`, `ze_api`, `ze_plugin` or `ze_memory` directly, or
when `ze-seed` imports `ze_api`.

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
make test-pg         # real-Postgres tests (needs Docker or ZE_TEST_PG_URL); not part of test-py
make test-all        # test-py with slow tests, then test-web
make test-web        # @myguyze/ze-ui + React web app (vitest)
make typecheck-web   # tsc --noEmit for ze-web and @myguyze/ze-ui

# Code quality
make lint            # ruff lint across the repo (ruff.toml excludes .claude/)
make format          # ruff format + fix across all Python packages

# Evals
make dev-eval        # backend for evals — no dev seed data, PUBLIC_URL cleared (background jobs still start)
make eval-server     # start MCP eval server (requires dev-eval running; see docs/eval.md)
make calibrate-commitment-intake  # LIVE System One + old-pipeline baseline over eval/calibration/commitment_intake.jsonl; costs credits (--set holdout3 gave the one verdict on 2026-10-16 and is spent; --check-sets offline)
make calibrate-routing     # LIVE System One run over eval/calibration/routing.jsonl; costs credits (--check-sets is offline)
make calibrate-skills      # LIVE System One run over eval/calibration/skills.jsonl; costs credits (--recall: offline shortlist recall)
make calibrate-open-query # Local, free: open-query detector sweep over eval/calibration/open_query*.jsonl (--check-sets offline; one held-out verdict)
make calibrate-loop-gate  # LIVE System One + Haiku baseline over eval/calibration/loop_gate.jsonl; costs credits (--set holdout = the one verdict run; --check-sets offline)
make calibrate-corroboration  # LIVE System One + E5 baseline over eval/calibration/corroboration.jsonl; costs credits (--set holdout = the one verdict run; --check-sets offline)
make calibrate-complexity  # LIVE System One over eval/calibration/complexity.jsonl; costs credits (--check-sets offline; --set holdout = the one verdict run)
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
- **LLM JSON**: Parse every JSON reply from a model with `parse_llm_json(raw, expect=dict|list)`
  (`ze_agents.llm_json`, re-exported as `ze_sdk.parse_llm_json`). Models wrap JSON in markdown
  fences or prose even when `response_format` asks for bare JSON, so never call `json.loads` on
  a model reply. It raises `LLMJsonParseError` (a `ZeError`); catch that at the call site.
  `ze-eval` has no Ze deps by design and keeps its own `parse_judge_reply`.
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
- Real-Postgres tests: mark with `@pytest.mark.pg`, skipped unless `ZE_TEST_PG=1`. Run
  `make test-pg` (needs Docker or `ZE_TEST_PG_URL`); `test-py` never starts Docker.

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

**Routes** — five places (World, Ask, Doing, Mind, Governance) declared in `shared/config/places.ts` (with the old-route redirect table) and built into `app/router/routes.tsx`. Plugin routes injected at runtime via `GET /api/v0/ui/manifest`.

### Native app interface

- The `NativeAppInterface` in `ze_api/interface/native.py` handles all outbound delivery:
  WebSocket frames when the client is connected, ntfy push notifications otherwise.
- The WebSocket endpoint lives at `/ws`. One connection at a time — a new connection
  displaces the previous one with close code `4000`.
- On connect, unread messages are replayed from `MessageStore` before new frames flow.
- Confirmation requests are sent as `{"type": "confirm_request", ...}` frames with `kind`
  (`write`, `budget`, `held`) and `items`; the client replies with
  `{"type": "confirm", "id": "...", "choice": "approve"|"deny", "edits": {...}}`.
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
schedules. Agent config (description, model) lives on
`@agent` class attributes in Python — not in YAML.

Hot-reloaded on SIGHUP without restart.

## Adding a new agent

1. Write a spec first via spec-kit: `/speckit-specify` creates `specs/phases/NNN-<name>/spec.md` (see `specs/README.md` for the pipeline and index).
2. Create the agent in the appropriate package — `ze_personal/agents/`, `ze_messenger/agents/`,
   `ze_prospecting/agents/`, or `ze_calendar/agents/` — decorate with `@agent` from
   `ze_sdk`, subclass `BaseAgent` from `ze_sdk`.
   Put `description`, `model`, `tools`, and `timeout` as class
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
Add types to `plugin_deps` in `ze_api/wiring/container.py` only when the plugin
constructor needs a shared service not already in the dep map (phase 47b).

## Migration ownership

Every package that owns database tables owns its own Alembic migration chain.
`ze_api/cli/migrate.py` is a meta-runner: it discovers all chains via `version_locations`
and runs them against a single `alembic_version` table.

| Package | Branch prefix | Tables |
|---|---|---|
| ze-core | `zc` | routing_log, llm_cost_log, goals, goal_milestones, goal_gates, persona_state, LangGraph checkpoints, messages, sessions, pending_confirmations, messages.rollback (`zc032`), messages.screen_context (`zc039`); capability_overrides dropped (`zc034`); routing_log.complexity and routing_log.model_selected dropped (`zc035`, phase 182); user_facts, episodes, user_profile dropped (`zc037`) |
| ze-automation | `zc` (continues ze-core chain) | held_writes (`zc033`), goal_execution_traces, goal_suggestions (stuck goals col, reuse hint col), workflows, workflow_executions, workflow_revisions, accountability_anomalies, goal_learning_* (`zc030`; drops the old goal_learnings) |
| ze-personal | `zc` (continues ze-automation chain) | contacts, contact_channels, contact_sources, insights, episodes.contacts_extracted, user_channels, user_channel_watermarks (`last_outcome`, `last_outcome_at` in `zc040`), thread_channel_map (contact_relationships dropped in `zc029`) |
| ze-memory | `zm` | memory_entities, memory_facts, memory_episodes, memory_events, memory_task_state, memory_profile_facets, memory_relationships, memory_signals, memory_session_summaries, memory_retrieval_cache, memory_dream_*, memory_episode_metadata, action_records, procedure_* (`zm022`–`zm023`; replace memory_procedures), feedback_records (`zm024`), action_records JSON repair + subject-key indexes (`zm025`) |
| ze-onboarding | `zo` | onboarding_sessions, onboarding_steps, onboarding_seeds |
| ze-correlation | `zcor` | correlation_hypothesis |
| ze-worldstate | `zw` | open_loops, open_loop_sources (`zw003`), open_loops.reminder_id (`zw004`), open_loops.confidence_prior / confidence_changed_at (`zw005`) |
| ze-proactive | `zpro` | push_log, notifications, notifications.target_parent_id (`zpro005`), interruption_settings, proactive_job_runs |
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
- For non-plugin core packages (ze-core, ze-memory, ze-onboarding, ze-correlation, ze-proactive, ze-ingestion, ze-automation, ze-worldstate, ze-skills, ze-workspace, ze-collision, ze-priority): add an explicit `_ZE_*_VERSIONS` constant in `ze_api/cli/migrate.py`.
- Use `depends_on` in migration files for cross-package ordering (e.g. ze-prospecting depends on `zc005` for the contacts table).

## LangGraph graph flow

```
preprocess (image → caption) → [inject_routing_context, when a plugin adds a pre_route_node]
  → resolve_screen (screen context → screen note, before routing) → embed_route → (compound?) → decompose → fetch_context → match_skills → choose_tier → preflight
                ↘ fetch_context ↗

preflight → blocked (disabled agent) → END
          → budget pause (113, before the turn) → execute_tool
          → execute_tool ⇄ await_write_confirmation  (one pause per turn for all parked writes; max 3 rounds)
            execute_tool → correlate → surface_loops → (compound?) → synthesize → record_trace → write_memory → END
                                                                   ↘ record_trace ↗
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
| 92 | Agent Activity Heatmap — calendar heatmap of agent usage by day; `GET /api/v0/activity/heatmap` aggregates `messages.trace`; section on Usage (`/costs`) using `@uiw/react-heat-map`; removed by phase 190 (route, aggregator and chart) | Implemented |
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
| 113 | Proactive/Concurrency Hardening Sweep — three independent reliability fixes: `pending_confirmations` + in-process `pending_configs` rekeyed from `thread_id` to `request_id` (`zc027`) so concurrent confirmation gates on one thread can't clobber or cross-cancel each other; opt-in `budget:` config block + `SpendBudgetChecker`/`ze_core/telemetry/pricing.py` composed into `capability_check` (strictest-wins with `CapabilityGate`), holding execution via the existing `AWAIT_CONFIRMATION` gate when session/day spend would exceed a configured ceiling; `push_log` idempotency key + unique index (`zpro003`) turns `LoopSurfacer.log_push`/`PushSweepJob` from notify-then-log into claim-then-notify (`claim_push`/`release_push_claim`), closing the concurrent-sweep double-notify race and rolling back the claim on notifier failure (the push-claim half is superseded by 177: the governor owns the budget claim) | Implemented |
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
| 127 | User-Directed Priority Override — `PriorityOverride` (`ze-priority`'s first store, `zpri` migration chain), snapshot view + drag reorder + conversational `reprioritize_item` tool, decaying/pinned overrides merged at render time (only REST and `TurnSurfacing` did this until phase 198 moved the merge into `PriorityView`), `ze_collision` skip rule narrowed to `(source_function, provenance)` so user-vs-executive priority disagreement is observable | Implemented |
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
| 163 | Speech-act System One — post-turn fact admission judged by System One (`speech_act`/family Choice + biography Noul), pure-code persist/hold/skip, Haiku value writer on persist, Haiku judge on skip, single attempt (`evaluate(max_attempts=1)`), judgments on the trace; on in the shipped config with bars calibrated 2026-10-09 (`make calibrate-speech-act`); superseded in part by 173: conversation fact admission now runs inside the commitment intake, `speech_act_judge.py` is deleted, `fact_judge.py` keeps the family and biography questions, and `make calibrate-speech-act` became `make calibrate-commitment-intake` | Implemented |
| 164 | Routing Choice After E5 — E5 stays the shortlist; a typed System One Choice decides single-specialist trust and a graded complexity question replaces the word-count classifier (depends on 162); shipped off (the 2026-10-09 calibration found no safe `choice_trust`); enabled by phase 167 | Implemented |
| 165 | Response Feedback and Retry — thumbs up/down on assistant replies as append-only `FeedbackRecord` evidence (`ClaimKind.FEEDBACK_RECORD`, licensed to Perception only; `feedback_records`, `zm024`), linked to the reply's `MessageTrace`, no consumer in v1; safe Retry regenerates the latest reply with write tools blocked (`retry_mode`; extended by 180), decided server-side by `retry_eligibility` from trace effect metadata; `messages.replaces`/`replaced_by` (`zc031`); every `WRITE` tool declares `reversibility` | Implemented |
| 166 | System One Skill Gating (O3) — E5 shortlists skills down to `shortlist_floor`; one batched System One Choice (shortlist ∪ `none`) plus a Noul `needs_skill` picks at most one automatic skill (a deliberate narrowing of 114; explicit `/skill-name` still stacks); a below-`match_threshold` apply is marked `below_floor` on the trace; `match_skills` appends its judgments; surface `system_one.surfaces.skills` shipped off with null bars until `make calibrate-skills`, then enabled 2026-10-12 with `choice_trust` 0.75, `needs_skill_hold` 0.6, `shortlist_k` 5; no suggestion UX | Implemented |
| 167 | Routing Choice Criteria — fixes the 164 held-out failures: companion no longer claims "explain X"; optional `routing_criteria` on `BaseAgent` (Choice text, falls back to `description`; E5 still embeds `description`); name-free Choice instructions and a stronger `none` criterion; `shortlist_k` 9 chosen by offline recall on three calibration sets (9 of 10 agents, so E5 filters little for the Choice; it still drives the 160 skip path); `eval/calibration/routing_holdout2.jsonl` and the opt-in `companion_research_check.py`. Surface enabled (`choice_trust` 0.5, `multi_specialist_hold` 0.5, `complexity_lookup_max` null) under an amended acceptance rule | Implemented |
| 168 | Loop Extraction Gate (O4) — one batched System One request asks three Nouls (`is_open_concern`, `resolves_existing`, `explicit_declaration` on conversation only); pure `decide()` in `ze_worldstate/loop_judge.py` maps them to resolve / create-declared / create-suspected / hold; Haiku only writes the title (and optional `implied_window_days`) after a positive gate; `LoopInflow` (`admission.py`) owns gate and commit; conversation gate runs in `write_memory` beside the fact extractor (rows on `MessageTrace.judgments`, fire-and-forget commit), worldstate `conversation_memory_hook` deleted; email/calendar/ingestion run the gate, log judgments, and write no trace rows; off, uncalibrated, skip or invalid → the 109 Haiku gate; surface `system_one.surfaces.loop_gate` enabled 2026-10-12 (`loop_hold` 0.75, `explicit_hold` 0.85, `resolves_hold` 0.8) after an `ENABLE` verdict for EN and PT on the held-out set; the 109 Haiku fallback now parses Haiku's fenced JSON (before 168 it did not, so production created no loops); no migration; superseded in part by 173: conversation turns moved to the commitment intake, so the loop gate now asks two Nouls (`is_open_concern`, `resolves_existing`) for email, calendar and ingestion only and `loop_gate` no longer carries `explicit_hold` | Implemented |
| 169 | Loop Track Tool — `track_loop(title, window_days)` on the `loops` agent starts tracking a concern the user explicitly asked Ze to keep in mind; injected `LoopTracker` (`ze_worldstate/tracking.py`) returns one of four outcomes (`created` active/`user_declared`/PRIORITY/0.9 via the contribution seam, `confirmed` a suspected match, `reinforced` an active match, `revived` a drifting match), optional `window_days` (default 7, clamp 1-365); `LoopStore.transition(..., user_asked=True)` adds the only `drifting → active` edge and `stamp_declared()` writes the confirmed/revive field set in one statement; `write_memory` skips the loop gate on a turn where `track_loop` succeeded (`track_loop_succeeded` in `ze_agents/nested_tools.py`); opt-in `strip_track_claims` honesty guard (EN + PT) on `enforce_domain_cancel_confirmations`, on for `LoopsAgent` only; `eval/scenarios/loops.yaml` and two routing training rows; drift sweep stays inert for declared loops until phase 170; no migration | Implemented |
| 170 | Executive Repair — drift fires on the deadline (`active AND drift_deadline <= now()`) and `record_corroboration` moves the deadline on new evidence; `list_stuck` returns one row per goal from the earliest fired open gate; loops carry evidence (conversation and email turn episodes, ingestion refs; calendar none) and the push grounding gate checks the loop title; the priority snapshot returns `{items, sources_failed}` and accepts `source_kind: relationship`; dead code and unread config removed; real-Postgres test harness (`make test-pg`); no migration | Implemented |
| 171 | Loop Confirmation — suspected loops reach the user: the `/loops` page lists them, one confirm (`confirm_loop` tool or page) stamps confidence 0.9 and a 7-day deadline like a declaration, `track_loop` reports `tracking_earned`; at resume Ze asks about up to 3 suspected loops (7-day cooldown in `push_log`); recap capped at 5 loops and the explicit "what's open" answer at 10; E5 `OpenQueryDetector` (`ze_priority/open_query.py`) replaces the "what's open" regex; no migration | Implemented |
| 172 | Corroboration Promotion — an independent source that matches a `suspected` loop is judged by one System One Noul `same_concern` (state = loop title capped at 200 + inflow + capped text, one attempt); pure `decide()` in `ze_worldstate/corroboration_judge.py` against two bars (`corroborate_hold`, `promote_hold`); `corroboration.py` links the evidence and raises confidence (`min(0.6, 1-(1-c)(1-0.5·s))`, stays suspected) or also promotes to `active` at `GREATEST(confidence, 0.7)` with a 7-day drift deadline in one UPDATE guarded by `state='suspected'`; independence is a pure code rule (source key new to the loop, evidence not already linked, key not on a matching dropped loop) and a non-independent match makes no request; origin rows are written on every create with a key; new table `open_loop_sources` (`zw003`) records the origin and each counted corroboration; REST gains `promoted`/`source_inflows`/`sources` and the `/loops` row shows "Promoted · seen in: …"; `make calibrate-corroboration` (E5 cosine 0.75 baseline); surface `system_one.surfaces.corroboration` ships off with null bars until a held-out `ENABLE` | Implemented |
| 173 | Commitment Intake — one System One request per conversation turn replaces the 163 speech-act and 168 conversation loop-gate requests (executive-function finding F4: a reminder was double-booked as a declared loop): a commitment Choice (`reminder, loop, goal, waiting_on, fact, forget, ingest, clarify, none`) plus the family and biography Nouls (fact) and the `is_open_concern`, `explicit_declaration` and `resolves_existing` Nouls, one batch with `max_attempts=1`; pure `decide()` in `ze_worldstate/commitment_judge.py` and `CommitmentIntake` in `intake.py`; a turn that created a reminder or goal creates no loop and persists no fact, and links a matching loop (`reminder_id`, `zw004`; `IntakeAdmission.links`); a `waiting_on` Choice never resolves and writes nothing (label only until phase 174); an unsure reminder or goal falls through to the loop rules; the Haiku fallback `speech_act` shrinks to `fact, forget, ingest, clarify, none`; `/loops` rows show "Has reminder" and "Linked goal" chips; `make calibrate-speech-act` replaced by `make calibrate-commitment-intake`; surface `system_one.surfaces.commitment_intake` enabled 2026-10-16 with frozen bars `choice_hold` 0.7, `family_hold` 0.7, `biography_hold` 0.55, `loop_hold` 0.6, `explicit_hold` 0.95, `resolves_hold` 0.8 (160 tuned rows) after two `KEEP OFF` held-out verdicts and an `ENABLE` verdict for EN and PT on a third blind set of 147 rows (zero duplicate bookings, zero false creates, fact precision 1.00, loop precision 1.00); migration `zw004` | Implemented |
| 177 | Interruption Governor (part 1) — one governor for every proactive push: `PushKind` (class requested/accountability/discretionary + urgency) registered process-wide, pure `decide()` in `ze_proactive/governor.py`; the shared daily budget (`proactive.budget.max_pushes_per_day` default 5) covers every discretionary push; quiet hours (`interruption_settings`, ship off) hold accountability and discretionary pushes, `QuietHoursReleaseJob` releases them with one summary buzz; `notify()` is the only send path (`push()`/`push_notification()` deleted); ntfy priority low 2/normal 3/high 5 and a `buzz` flag; REST `GET/PUT /api/v0/notifications/quiet-hours` + a Settings form; cron catch-up (`proactive_job_runs`, `catch_up_max_age_hours`), workflow catch-up, late calendar reminders; migration `zpro004` | Implemented |
| 180 | Retry Rollback — Retry undoes the reversible actions of the latest reply, then regenerates it. Reversible tools return a per-call `undo_payload` (`ze_sdk`) that `call_tool` stores on `ToolCall.undo` and the trace; `retry_eligibility` builds a public plan (entry ids = hash of message, call index, tool, args), the client confirms it as `confirmed_plan`, and the server recomputes it under the thread lock (`undo_not_confirmed` / `plan_changed`); `run_rollback` (`ze_core/conversation/rollback.py`) runs each undo through the owning agent's `BaseAgent.run_undo` with no model call and records each entry on `messages.rollback` (`zc032`; states `partial`, `rolled_back_awaiting_confirmation`, `rolled_back_retry_failed`, `superseded`); one retry policy (irreversible writes refused, reversible writes run under the normal gates, a confirmation pauses the retry); `message_rollback` frame, `retry_partial`, `history_unavailable`; `remember_fact` and priority overrides restore what they displaced; web two-step consent, rollback notice, trace `RollbackSection` | Implemented |
| 181 | Irreversible Write Confirmation — every WRITE tool that is IRREVERSIBLE asks first unless it declares `asks_first=False` with a reason: `call_tool` parks it, `LoopParked` is caught at the delegate/subtask boundary, one `await_write_confirmation` pause per turn (`confirm_request` frame with items; at most 3 rounds, a 4th is `refused_over_cap`), resume runs exactly the approved calls before any model call; approval is an `ApprovedCall` built only from park state (model `_` args are stripped, injected deps win and are hidden from schemas); one item per identical `(tool, args)` (repeat gate `duplicate`); deny/timeout give a code-guaranteed "Okay, I didn't <effect>."; the 144 veto runs before pre-approval; summaries name the target (`summarize` gets deps); goal gates/suggestions/workspace reset use `kind: "prompt"` frames; a confirmation push rings the bell without a chat message (`PushKind.in_chat`); intents, modes, `CapabilityGate` and capabilities REST/WS hard-cut (`zc032`); per-step `approved_writes` for workflows/goals, unplanned writes hold in `held_writes` (`zc033`, 24 h, `write_approval_held` push, REST `/api/v0/held-writes`, `HeldWriteExpiryJob`); eval `/eval/confirm` + `confirm:` scenario step | Implemented |
| 182 | Complexity Routing — routing always assigns the agent's full model; the `choose_tier` node runs after `match_skills` and asks one System One Noul (`needs_deep_reasoning`, `ze_core/routing/tier.py`) only for a single-agent turn whose agent declares a different `model_simple`; `model_simple` runs only when the answer is at or below `simple_max`; the complexity Score, `complexity_lookup_max`, the word-count classifier and `RoutingEnvelope.complexity` are removed; the surface is enabled at `simple_max` 0.40 (`system_one.surfaces.complexity`) after a held-out ENABLE in English and Portuguese on 2026-10-16; the code default without the config block is off; `MessageTrace.tier` (`TierTrace`: agent, tier, decided_by, model) reaches REST, the `trace_update` frame and the trace panel's Routing section; `routing_log.complexity` and `model_selected` are dropped (`zc035`); `make calibrate-complexity` runs the tuned and held-out calibration | Implemented |
| 183 | Web Shell and Tokens (W1) — the Jarvis HUD becomes the app frame: tokens in `shared/styles/ze.css` (self-hosted Saira, Michroma, JetBrains Mono), HUD primitives in `shared/ui/hud`, five places (World, Ask, Doing, Mind, Governance) in `shared/config/places.ts` with a redirect table for the old routes, a top bar, strip, Presence module and sticky Ask bar, a phone bottom bar; the orb follows real signals for the Ask thread through `entities/presence` (pure `nextPresence`) and acts like a curious pet while idle (`gaze.ts`); the Ask bar opens a contextual overlay that sends on the thread selected in Ask; old pages render as interim sections of their place; palette is a Governance setting; floating launcher, organ nav and `nav-routes.ts` deleted; no backend change | Implemented |
| 184 | Composed Answers and Claim Posture (B1) — `ClaimPosture` on every primitive, set only by code from the stored record (a model-supplied `claim` is dropped); new `headline`, `claim_card`, `claim_timeline` primitives; `ze_priority/compose/` `WorldComposer` builds slipping, decisions and topic answers from stored records (parallel read, per-source failure named); preset chips send `context.compose`/`topic` and `fetch_context` reroutes to companion under a 2 s timeout, typed questions use `show_slipping`/`show_decisions`/`show_topic`; topic matching keeps an item that shares a topic word or has E5 cosine ≥ 0.90; derived `failure_summary` on workflow runs; goal list progress fields and `STUCK_IDLE_DAYS`; `notifications.target_parent_id` (`zpro005`) and notification deep links; inline loop mentions are claim cards (`open_items` removed) | Implemented |
| 190 | Governance (W6) — `/governance` answers "is Ze behaving?" in five modules (Spend, Attention, Data, Connections, Files) under `pages/governance` and `widgets/{spend,attention,data,connections,files}`; new `SeriesSpark` in `shared/ui/hud`; redirect entries gain `hint`/`hintMap` so `/settings`, `/data`, `/workspace` land on `/governance#connections`, `#data`, `#files`; Spend compares the last 7 days' daily average with the 30-day average; Attention shows the 185 push budget as `Dots`, held count and recent push outcomes beside the quiet-hours form; Files is read-only; hard cuts: WS `reset_preview`/`reset`, `GET /api/v0/activity/heatmap` and its aggregator, the costs/data/settings/workspace pages and widgets, `heatmap-chart`; the local "Reset configuration" became "Forget this server"; Governance publishes `focused_module` (195); no migration | Implemented |
| 187 | Ask / Assemble (W3) — `/ask` is the Assemble canvas. `entities/conversation` (one reducer per thread, the seven conversation frames) replaces the per-instance `useChatWorkspace`; `features/turn-stream` mounts one `TurnFrameHandler` in the shell (rail flags, orb, ack, delivery watchdog that pauses on a confirmation), `sendTurn` is the one send path, and a frame registry test enforces one state owner per frame. `widgets/assemble` draws each reply as a sentence plus a module per component (A·NN ids, pin, dismiss, cascade from the orb, Chat about this), places confirmations and Retry in the canvas and the overlay, and the Ask bar is on every place with a workspace attach. `@myguyze/ze-ui` takes a `classNames` map and `renderHeadline`. The trace is a rail of instruments (Signal path, Routing, Memory, Tools, Judgments, Reversal, readouts) drawn only from `MessageTrace` and `trace_update`; `ToolCallTraceResponse` gains `agent` and `call_index`, and `trace_update` gains `compaction` and `resume_recap_applied`. A displaced window shows "Ze is open in another window · Use here". Deleted: `widgets/chat-workspace`, `features/chat-side-panel`, `features/load-chat-history`, `pages/chat`, the starfield effects, the `/jarvis` composition; no migration | Implemented |
| 187b | Trace Telemetry — one in-process `TurnTelemetry` recorder per turn (`ze_core/telemetry/turn.py`, a registry keyed by thread that survives a confirmation pause) measures the turn on the server on one monotonic clock; `timed()` (`orchestration/timing.py`) wraps every graph node, including plugin and workflow nodes, and sends one partial `stages` frame per node through a non-blocking ordered sender (a frame stuck for 1 s is dropped; the committed trace is the complete record, drained before it goes out); `CostTracker.record` adds each model call, so the stamped trace carries `stages`, `turn_duration_ms`, `paused_ms`, `usage` (tokens and cost per model, largest-prompt context fill, System One tokens apart) and `telemetry_partial`; `total_duration_ms` is hard-cut to `tool_duration_ms`; the router puts `threshold`/`gap_threshold` on every envelope and the trace carries `routing_scores` (top 9) and `routing_thresholds`; judgment rows carry `surface` and the `bar` in force (routing, skills, complexity, commitment intake); `ToolCall` gains `call_id` and `started_at`, `ParkedWrite.trace_call_id` makes a parked call and its approved run one id, and `call_tool` hands every finished call (delegate wrapper included) to `AgentContext.tool_sink`, which ze-core sends as truthful live tool rows (the `on_tool_end` partial is deleted); the memory partial gains `extraction_confidence`; web: `toTraceFrame` and `useTraceStore` merge server stages and tool rows by `call_id`, the arrival stamps and `MessageTracePanel` are deleted, and the six instruments read the server fields; no migration | Implemented |
| 186 | World (W2) — the home at `/` (`pages/world`, `useWorld` joins nine queries plus the pending-confirmation store): the Field (`widgets/world-field`: time left × how sure, claim-kind marks, a Slipped band that wins over the deadline, a trail only from `confidence_prior`, reorder and pin by drag or keyboard, a ranked list on phones), Needs you (held writes through one `HeldWriteCard`, goal gates through `features/answer-gate`, suspected loops, chat confirmations), Doing now, Loops, Touched and While you were away; `?focus=<kind>:<id>` links (`focusHref`, `notificationHref` in `shared/lib`); the shell's `rail-slot` takes Needs you and Doing now under Presence; World invalidates on `message`, `notification` and `refresh` frames; the four priority hooks throw on a failed read so an error never reads as "nothing tracked"; deleted: `pages/loops`, `pages/priority`, `widgets/loop-review`, `widgets/priority-snapshot`, `WorldInterim`, the bell's held-write list and `?confirm=`, and ze-calendar's Reminders page and `getRemindersPage`; no migration | Implemented |
| 188 | Doing (W4) — `/doing` answers what runs without the user, what it did and what waits for it, in five modules (Needs you, Goals, Workflows, Runs, Skills) under `pages/doing` and `widgets/{doing-needs-you,goals-board,workflows-board,runs,skills-queue}`; `/doing/goals/:id` (gate first, `milestone-field`, learnings with review, traces as a readout, linked loops with their reminders) and `/doing/workflows/:id` (restyled flowchart, live execution, runs with `failure_summary`, revisions); `features/answer-gate` gains the `goal_stuck` variant (Redirect, Pause, Abandon asks once, 15 s timeout line); workspace runs are new in the web app (`useWorkspaceRunsQuery` polls every 5 s while one runs, `useCancelWorkspaceRunMutation` treats 404/409 as a plain outcome, `isAlarm` is coral only for unattended `failed`/`timed_out`); hard cuts: the Goals, Workflows and Skills pages and widgets, `GoalCard`, the "Current definition" banner, `stepsDifferFromSnapshot`, `DoingInterim`; `goalsPath()`/`workflowsPath()` return `/doing#goals|workflows`; no backend change, no migration | Implemented |
| 185 | World Data Gaps (B2) — four values the new places need over REST. `ze_proactive.attention_budget.budget_status()` is the one rolling-24-hour budget count (`PushLogStore.window_sent_at` replaces `count_sent_within_hours`); `GET /api/v0/notifications/budget` (`used`, `remaining`, `next_slot_at`, `held_count`, `quiet_hours_active`) and the budget fields leave `QuietHoursResponse`; `listNotifications` gains `delivery`/`push_class`/`since` and `urgency`/`delivered_at`; `GET /api/v0/proactive/job-runs` lists the last run per job; `zw005` stamps `open_loops.confidence_prior`/`confidence_changed_at` on a real confidence change (corroboration's promote path writes once) and loop rows gain `drift_deadline`/`confirmed_at`; loop claim postures fill `confidence_from`; `GET /api/v0/hypotheses` + `POST .../feedback` (feedback now filters the push sweep, `PriorityView` and `who_is_on_project`); `GET /api/v0/reminders` in ze-calendar | Implemented |
| 189 | Mind (W5) — `/mind` (Beliefs, People, Find an entity, Procedures) and `/mind/:entityId` replace the Memory and Graph interim pages; `claim_kind` on feed items and entity facts, ordered neighbours with `neighbour_total`, `searchEntities` (no migration); shared `shared/lib/claim-posture.ts`, `entities/hypothesis` and an "I suspect…" list; screen context and Chat about this; the 3D graph, three.js and the Contacts nav entry are deleted | Implemented |
| 192 | Voice Input Transport (B3) — `POST /api/v0/voice/transcriptions` (`transcribeVoice`) measures a recording with `ffprobe`, transcribes it with `whisper` and returns a `transcription_id` valid 10 minutes; a message that names a live id runs as a voice turn with `MessageTrace.input` (modality, duration, edited), and no transcript is kept; the audio-in-turn path is cut (`RawInput.audio`, `AgentState.audio_data`); `ffmpeg` in the ze-api image; spend flow `transcription`; no migration | Implemented |
| 193 | Voice and Polish (W8) — voice input in the Ask bar (`features/voice-input`: `MediaRecorder` in WebM/Ogg/MP4, an analyser level the orb reads per frame, upload to `transcribeVoice`, the transcript fills the bar and the next send carries `context.voice.transcription_id` from Ask and through the overlay outbox; 115 s stop with a countdown from 105 s, hold `V`, Retry vs Record again vs Try again, a generation number per start); Presence `voice` states (`listening` while recording, `thinking` "transcribing"); `features/ambience` (the drone moved from the prototype, toggle in the Presence head, `ze.ambience`, gesture arming, no auto-start under reduced motion, ducked while recording); the Jarvis prototype, its route (no redirect), notes and palette test case are deleted; client queries throw on error; unreferenced style rules and layout components removed; DESIGN.md refreshed; no backend change, no migration; the critique ran as one single-context pass per place (scores 30-33 of 40); focus rings asserted per control on every place; the reduced-motion Ask run used a stubbed websocket (the test API's model key was over its limit) | Implemented |
| 195 | Screen Context Awareness — the web app sends a typed `ScreenContext` (place, route, `subject`/`selection`/`visible` refs, focused module, canvas, `captured_at`; `ze_agents/screen.py`, `from_wire` never raises) and a `resolve_screen` node runs before `embed_route` on both pre-route branches (and the workflow graph). `ZePlugin.screen_resolvers()` registers one resolver per ref kind (`ze_core/screen/registry.py`, a duplicate kind fails startup; 16 kinds across automation, worldstate, memory, skills, workspace, correlation, proactive, personal, calendar, news); `build_screen_note` writes one honest note of at most 1,200 characters (300 ms per resolver, 800 ms total, first subject never cut, `missing`/`changed`/`failed`/`timeout`/`cut` stated) that `fetch_context` hands to the agent as `screen_context_note` (184's preset summary moved to `preset_note`). The context is stored on each user message (`messages.screen_context`, `zc039`) so Retry replays it; `MessageTrace.screen` reaches REST, the `trace_update` frame and the trace panel. A `chat_about` turn with a subject routes to the subject kind's owner agent (`ze_core/screen/owners.py`, `routing_method: screen`); the routing judge reads one subject line for typed asks only when `system_one.surfaces.routing.screen_hint` is true (ships off). Web: `entities/screen-context` store and `useScreenPublisher`, one send path in `useChatWorkspace`, the "Chat about this" chip (`Module.onChatAbout`, `c` key, `claim_card`) opening the overlay with suggestions and a curious-pet orb glance. Old `screen`/`goal_id`/`workflow_id`/`execution_id` fields and `_build_screen_context_note` deleted. Eval: scenario `setup:` rows and `{{name.field}}` substitution (`ze_eval/fixtures.py`), `eval/scenarios/screen_context.yaml`, `make calibrate-routing ARGS=--check-sets` and `eval/calibration/routing_screen.jsonl` (offline; no live calibration run). The screen_context scenarios ran live (first run 10 of 26 passed; chat_about 9 of 15 after owner routing; see the phase Handoffs); the chip capture is deferred to phase 193 | Implemented |
| 194 | Accountability Surfaces (B4) — five read routes for the web places: `GET /api/v0/actions` (`listActionRecords`: the action ledger by goal, workflow, workflow run or workspace run, keyset cursor on `(occurred_at, id)`; `ActionRecordStore.list_by_subject` and the closed `ActionSubjectKind` map in ze-memory; the workflow-finished record now carries `workflow_id`), `GET /api/v0/collisions` (moved from the eval router to the product API, bad input is 422), `GET /api/v0/system/models` (`getModelSettings`: `complexity_enabled` is `ComplexitySurfaceConfig.calibrated`), `listLoops` with repeatable `state` and `since`, and `GET /api/v0/channels/status` (`listChannelStatus`); the inbound poll job records `ok`/`auth_failed`/`failed` on `user_channel_watermarks` (`zc040`, never moves the watermark; a never-working channel is registered on its first failure; push channels report `unknown`); `ze_google.is_auth_failure` keeps `google.auth` out of the messenger plugin; `ResetService`, its script and `make reset-personal-state` are deleted; fix: action records were written as double-encoded jsonb under the pool codec, repaired by `zm025` (which also adds the per-subject-key partial indexes); datetime query values need a timezone offset (422); a 401 from Google counts as `needs_reauth` | Implemented |
| 191a | UI Primitives v2 — typed `PrimitiveAction` (`ask`, `tool`, `navigate`, `compose`) replaces string button actions; a `tool` action names an agent and one of its write tools that opted in with `@tool(ui_action=True, done_phrase=…)` and runs as a `ui_action` WS frame through `BaseAgent.run_action` and `call_tool`, so every write gate applies (asks-first writes send a `confirm_request`; the in-process gate pops on first confirm, times out, is superseded by a new turn, replays on reconnect; one `ui.tool_action` ledger record per run); `ui_action_result` frame; `ui_version` "2.0" on live message frames and plugin pages, unversioned stored trees render as legacy; `parsePrimitiveTree` validates node by node with a fallback node for unknown types; new `entity_facet`, `stat_row`, `claim_list`, `sparkline`, `card` and keyed `table`; render tools for stat row, keyed table and sparkline; `ProgressBar` removed; shared fixtures in `packages/ze-ui/fixtures/` and the dev-only `/dev/primitives` gallery; no migration | Implemented |
| 191b | Plugin Modules in Slots — plugins add no pages. `UiContribution.kind` is `module` (a `slot` — `mind.entity`, `doing.run`, `governance.connections` — and an async `provider(ModuleSubject) -> ModuleResult`), `preset` (an Ask Try chip, at most two show) or `settings_section`; the page kind, `path`, `page_operation_id`, `show_in_mobile_nav` and `CORE_RESERVED_NAV_PATHS` are cut and an unknown kind fails startup; `GET /api/v0/ui/modules/{module_id}` (`getUiModule`) resolves the subject from Ze's own records, calls the provider under 3 s and refuses a view whose tool action names another plugin's agent, whose posture is not licensed for plugins, or that fails the primitive schema (502/504 plain lines); `request_module_refresh` sends a `module:<id>` refresh frame (`AppInterface.send_refresh`); ze-news contributes the preset, a Mind `Sources` module (articles tagged with a topic entity's name) and settings, its page is deleted; web `widgets/plugin-module` (`PluginModuleSlot`), 60 s visible polling, `/news` → `/ask`, the `:pluginPath` route, `pages/plugin-page`, `widgets/plugin-screen` and the `plugin` place are deleted; ze-personal's Contacts page stays for Mind › People; no migration | Implemented |
| 197 | Programmatic Tool Use — `run_tool_script` gives every agent with a data read tool one short Python script that calls those reads in one model turn; the script runs in the workspace sidecar as the `zescript` user with no network, resource limits and scratch only, and the sidecar fails closed (scripts are `unavailable` unless it runs as root with `zescript` and reports `scripts_isolated`; `ZE_SCRIPTS_ALLOW_UNISOLATED=1` is test-only); each inner call runs through `call_tool`, so every gate applies; writes are proposed in `finish(...)` and run after the script under the confirmation rules; `produces_ui` and `egress` keep screen and URL-reaching tools out of the stub; `workspace.scripts` limits; `max_llm_calls` eval cap; three successes with one tool signature propose a `tool_script` procedure for review in Mind › Procedures; no migration | Implemented |

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
- When implementing from an attached Cursor plan or a speckit phase: do not edit `plan.md`; use the pre-created todos. Tick a speckit `tasks.md` checkbox in the same commit that finishes the task.
- Ze's user-facing interface is the React web app (`ze-web`), not Telegram — do not describe Telegram-style UI capabilities to users.
- Only create git commits when explicitly asked. When asked to commit a large batch, split by logical phase or spec user story rather than one dump.
- Chat chrome: the trace is a module on the Ask canvas (a rail beside the answer, a dialog on phones), named **trace** (not "Ze's Mind"); sessions live in the Ask rail. Do not duplicate page titles already shown in the top bar.
- Discuss and pin spec scope before creating speckit files unless explicitly asked to write them.
- Implement multi-phase roadmaps in order: finish tests and mark the current spec Implemented before starting the next.
- Workspace is chat-first: interact via chat; the file map lives in Governance › Files (tree/info only), not a run console; do not bring back execution modes; unattended always has the computer.
- After a multi-spec batch is Ready to implement, leave a copy-paste handoff/goal prompt for the next session.
- Multi-floor Maestri status and rolling roadmaps: prefer portable HTML (or Maestro-hosted) openable in Maestro or outside Cursor — not Cursor Canvas or Cursor-native-only artifacts.

## Learned Workspace Facts

- `core/ops/ze-seed` (Phase 96) seeds dev data when `AUTO_SEED_DEV_DATA=true` (default on `make dev` / `make dev-full`); each run wipes the `seed-dev-*` namespace and re-applies narrative fixtures; plugins extend via `ZePlugin.seed_domains()`.
- `ze-email` was renamed to `ze-messenger` (`plugins/ze-messenger/`); Gmail inbound channel lives in `integrations/ze-google`.
- Plugins add no pages. `ZePlugin.ui_contributions()` returns modules (bound to a slot: `mind.entity`, `doing.run`, `governance.connections`), Ask presets and settings sections; `ze-web` reads them from `GET /api/v0/ui/manifest` and loads a module's tree from `GET /api/v0/ui/modules/{module_id}`; plugin REST routes mount via `rest_routes()`.
- `apps/ze-web` follows Feature-Sliced Design: `pages → widgets → features → entities → shared`; query hooks live in `entities/<name>/api/`.
- Chat inline UI uses `ze-components` `render_*` tools (stat row, keyed table, sparkline, table, metric, list, timeline, progress, confirm, form) rendered by `PrimitiveRenderer` below message bubbles. Button actions are typed (`ask`, `tool`, `navigate`, `compose`); a tool action runs through the write gates via the `ui_action` frame.
- `journal/` and `brag-output/` are gitignored local writing; treat as authoring notes, not product source.
- Web places (phase 183): World, Ask, Doing, Mind, Governance. All five have their own pages, no interim file remains and the prototype route is gone: `/` is the World page (Needs you and Doing now sit in the shell rail under Presence); Ask is the Assemble canvas in `pages/ask/ui/AskPage.tsx` (187); `/doing` holds Needs you, Goals, Workflows, Runs and Skills, `/doing/goals/:id` and `/doing/workflows/:id` the detail pages, and `/doing/goals`, `/doing/workflows`, `/doing/skills` redirect to `/doing#goals|workflows|skills`; `/mind` holds Beliefs, People, entity search and Procedures, and `/mind/:entityId` the entity view. The Ask bar on every place but Ask opens a contextual overlay that sends on the thread selected in Ask.
- Keep the phase 115 workspace sidecar (`core/ops/ze-workspace` + `sidecar/workspace`); chat-first map at `/workspace`; do not replace with Cloudflare Computer — borrow run-handle / exec-journal ideas instead.
- Perception/memory fact writes go through the contribution seam (`specs/arch/contribution-seam.md`): Phase 133 wraps writers; Phase 134 hard-cuts `memory_facts` onto shared claim vocabulary and removes public `propose_facts`.
- Arch roadmaps: experiential learning 135–139 (`action_records`, procedures); memory honesty 140–150 (`specs/arch/memory-honesty-roadmap.md`); companion-conductor 151–161 (`specs/arch/companion-conductor-roadmap.md` — companion sole speaker, fat `delegate_to_agent`, no `plan_sequential`/swarm; phase dir 151 is conductor ACI).
- Every `WRITE` `@tool` declares `reversibility` (plus `undo_tool`/`undo_note` when reversible, and `effect_phrase`); an undeclared WRITE tool fails registration. Retry eligibility reads it. IRREVERSIBLE tools ask first unless they declare `asks_first=False` with a reason. A `REVERSIBLE` tool returns `undo_payload(...)` per call, only in the clean case, so Retry can undo that exact call. Perception holds two licences: `FACT` and `FEEDBACK_RECORD`.
- Tool scripts (phase 197): `run_tool_script` is a harness capability with no opt-in; the stub is the agent's data read tools minus writes, `produces_ui` and `egress` tools. The script runs in the workspace sidecar (`zescript` user, no network; the sidecar fails closed and refuses unless isolated, and `ZE_SCRIPTS_ALLOW_UNISOLATED=1` is test-only) and needs `cap_add: [NET_ADMIN]` locally; without it `scripts_isolated` is false and scripts report `sandbox_unavailable`. Scripts are not verified on Fly: `fly.toml` sets no `NET_ADMIN`, and Ze runs locally. Unattended goal and workflow runs have no script runner.
- `.cursor/rules/` is gitignored; do not commit Cursor rules.
