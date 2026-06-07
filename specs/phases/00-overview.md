# Ze — System Overview

## Purpose

Ze is a personal AI assistant that routes user prompts to specialised sub-agents,
executes tasks with configurable permission levels, and maintains persistent memory
of user facts and interaction history. It is strictly single-user, self-hosted on
Fly.io, and accessed via Telegram.

## Core Design Principles

- **Minimise LLM calls.** Local sentence-transformer embeddings handle routing in
  the happy path. No LLM is invoked until an agent actually needs to act.
- **Configurability over automation.** Every agent action has an explicit permission
  mode (`Mode` class attribute on each `@agent`). Ze does not take write-risk actions
  autonomously unless the user has opted in.
- **Memory as editorial problem.** Agents propose facts and episodes; the user
  approves what is stored. Ze never silently writes to long-term memory.
- **Modular agents.** Each agent is isolated — its own system prompt, tool registry,
  model config, and intent map. Agents cannot call each other directly.
- **Spec-first development.** No module is implemented without a reviewed spec.
  Open Questions in a spec must be resolved or explicitly deferred before
  implementation begins.
- **Dependency injection throughout.** Every module accepts its dependencies as
  constructor arguments. FastAPI `Depends()` handles wiring at the API layer.
  Nothing reads from globals or `os.environ` directly except `ze/settings.py`.

## Monorepo Layout

```
ze/
├── packages/
│   ├── ze-core/        # Pure infrastructure — routing, memory, orchestration, telemetry
│   ├── ze-personal/    # Personal-assistant domain layer (ZePlugin)
│   ├── ze/             # Application — Telegram, Google, jobs, agents, API
│   └── ze-browser/     # Browser sidecar client (BrowserClient + tool)
├── specs/
│   ├── phases/         # Feature / phase specs (this directory)
│   ├── core/           # ze-core infrastructure specs
│   └── arch/           # Architecture decision records
└── docs/
```

### Package dependency graph

```
ze-browser  (no ze deps)
ze-core     (no ze deps)
ze-personal → ze-core
ze          → ze-core, ze-personal, ze-browser
```

## System Flow

```
User message (Telegram Bot API)
        │
        ▼
  [preprocess]  ──── transcribe voice / caption image (if multimodal)
        │
  [embed_route]  ──── cosine similarity ──── local sentence-transformer
        │
        ├─ confident + single agent ──────────────────────────────────────┐
        │                                                                  │
        └─ ambiguous / compound ──── [decompose] (Haiku via OpenRouter) ──┤
                                                                           │
                                                              [fetch_context]
                                                           (pgvector search)
                                                                           │
                                                           [capability_check]
                                                            (Mode on @agent class)
                                                                           │
                                              ┌────────────────────────────┼──────────────────────┐
                                              │                            │                      │
                                           EXECUTE                      DRAFT            AWAIT_CONFIRMATION
                                              │                            │                      │
                                       [execute_tool]             [draft_response]    [await_confirmation]
                                              │                            │             (graph paused,
                                              │                            │           AsyncPostgresSaver)
                                              └────────────────────────────┴──────────────────────┘
                                                                           │
                                                               [synthesize] (compound tasks only)
                                                                           │
                                                               [write_memory] (always runs)
                                                                           │
                                                  Response sent via Telegram Bot API
```

## Agent Roster

| Agent          | Primary Capability                                             | Package      |
|----------------|----------------------------------------------------------------|--------------|
| `calendar`     | Read, create, update, delete Google Calendar events            | `ze`         |
| `email`        | Read, draft, send Gmail messages                               | `ze`         |
| `research`     | Web search (OpenRouter web_search), summarisation              | `ze`         |
| `workflow`     | Multi-step plan execution, APScheduler-persisted               | `ze-personal`|
| `companion`    | Reasoning, thinking partner; contact/outreach tools            | `ze`         |
| `reminders`    | NL time parsing, APScheduler firing, proactive push            | `ze`         |
| `prospecting`  | Autonomous target research, browser extraction, outreach draft | `ze`         |
| `goal`         | Multi-week autonomous goal execution, milestone tracking        | `ze-personal`|

## Implementation Phases

| Phase | Scope                                                                                       | Status  |
|-------|---------------------------------------------------------------------------------------------|---------|
| 1     | `research` + `companion` only. Full stack vertical slice.                                   | ✅ Done |
| 2     | Memory (pgvector), capability gate, confirmation + draft UI.                                | ✅ Done |
| 3     | `calendar` + `email`, Google OAuth2, compound task decomposition.                           | ✅ Done |
| 4     | `workflow`, memory digest, routing log UI, capability config UI.                            | ✅ Done |
| 5     | Memory consolidation — dedup facts, expire stale, summarise episodes.                       | ✅ Done |
| 6     | User profile — synthesise facts + episodes into a structured portrait.                      | ✅ Done |
| 7     | Proactive Ze — morning briefing, workflow failure alerts, calendar reminders.               | ✅ Done |
| 8     | Insight engine — weekly synthesis of facts + episodes into actionable insights.             | ✅ Done |
| 9     | Cost telemetry — per-flow/agent token tracking, automatic cost reconciliation.              | ✅ Done |
| 10    | Multimodal input — voice transcription + image/vision support.                              | ✅ Done |
| 11    | Persona profiles + dials — named profiles, TARS-style dials, `/persona` cmd.               | ✅ Done |
| 12    | Contacts — person tracking, extraction from email/calendar/conversation, confirmation flow. | ✅ Done |
| 13    | Reminders agent — NL time parsing, APScheduler firing, startup replay.                      | ✅ Done |
| 14    | Progress messages — per-agent Telegram status messages, locale keys.                        | ✅ Done |
| 15    | Telegram commands — `/costs`, `/memory`, `/contacts` introspection.                         | ✅ Done |
| 16    | Agentic tool loop — LLM-driven ReAct loop in `BaseAgent`.                                  | ✅ Done |
| 17    | Prospecting agent — autonomous target research, browser extraction, outreach drafting.      | ✅ Done |
| 18    | Communication channel abstraction — `Channel` ABC, `EmailChannel`, contact channel handles. | ✅ Done |
| 19    | Goal Engine — autonomous multi-week goal execution, verification gates, milestone loop.      | ✅ Done |
| 20    | Package architecture reorg — ze_core pure infra, ze-personal domain layer, ZePlugin ABC.   | ✅ Done |
| 21    | Agent harness — hook points, step-level abort, multi-agent handoffs.                        | ✅ Done |
| 22    | Harness adoption — tool-call cap hook, research delegation, `/cancel` command.              | ✅ Done |
| 23    | Goal engine v2 — milestone context, execution traces, adaptive replanning, gate narrative.  | ✅ Done |
| 24    | Goal collaboration — goal-aware routing, steering, retrospective, weekly narrative.         | ✅ Done |
| 25    | Proactive goal suggestions — weekly LLM-generated goal proposals via Telegram.              | ✅ Done |
| 26    | Stuck goal detection — idle milestone/gate alerts, Telegram recovery actions.               | ✅ Done |

## Spec Index

### Phase specs (`phases/`)

| Spec | Module | Phase |
|------|--------|-------|
| `00-overview.md` | This document | — |
| `01-routing.md` | Embedding router | 1 |
| `02-capability-gate.md` | Capability gate (deprecated → see `core/03`) | 2 |
| `03-memory.md` | Memory system | 2 |
| `04-agents.md` | Sub-agent definitions (deprecated → see `core/01`) | 1–4 |
| `05-orchestration.md` | LangGraph graph | 1 |
| `06-openrouter-client.md` | OpenRouter client | 1 |
| `07-api.md` | FastAPI + Telegram webhook | 1 |
| `08-telegram.md` | Telegram Bot | 1 |
| `09-agent-tool-api.md` | Agent tool protocol | 4 |
| `10-phase3-google.md` | Calendar + Gmail agents | 3 |
| `11-persona.md` | Companion persona | 1–2 |
| `12-workflow.md` | Workflow agent + scheduler | 4 |
| `13-phase5-memory.md` | Memory consolidation | 5 |
| `14-user-profile.md` | User profile synthesis | 6 |
| `15-proactive-ze.md` | Proactive push infrastructure | 7 |
| `16-insight-generation.md` | Weekly insight engine | 8 |
| `17-cost-telemetry.md` | Cost tracking + reconciliation | 9 |
| `18-cost-aware-routing.md` | Complexity-based model selection | 9 |
| `19-multimodal-input.md` | Voice transcription + image captioning | 10 |
| `20-contacts.md` | Person tracking, extraction, confirmation flow | 12 |
| `21-telegram-commands.md` | `/costs`, `/memory`, `/contacts` commands | 15 |
| `22-reminders-agent.md` | Reminders agent | 13 |
| `23-eval.md` | End-to-end eval via MCP | — |
| `24-agentic-tool-loop.md` | LLM-driven ReAct loop in BaseAgent | 16 |
| `25-persona-profiles.md` | Named persona profiles + TARS dials | 11 |
| `26-prospecting-agent.md` | Prospecting agent + ze-browser sidecar | 17 |
| `27-channels.md` | Channel ABC, EmailChannel, contact handles | 18 |
| `28-goal-engine.md` | Goal decomposition, milestones, verification gates | 19 |
| `29-progress-messages.md` | Per-agent progress status messages | 14 |
| `30-agent-harness.md` | Harness hooks, step abort, multi-agent handoffs | 21 |
| `31-goal-engine-v2.md` | Milestone context, traces, replanning, gate narrative | 23 |
| `32-goal-collaboration.md` | Goal-aware routing, steering, retrospective, weekly narrative | 24 |
| `33-goal-suggestions.md` | Proactive weekly goal suggestions via Telegram | 25 |
| `34-stuck-goal-detection.md` | Idle milestone/gate detection, stuck alerts, recovery callbacks | 26 |

### Ze Core specs (`core/`)

| Spec | Module |
|------|--------|
| `01-agent.md` | `@agent` decorator, `BaseAgent`, registry |
| `02-app-interface.md` | `AppInterface` ABC, send/push/confirm contract |
| `03-capability-gate.md` | `CapabilityGate`, `Mode`, `GateDecision` |
| `04-routing.md` | `EmbeddingRouter`, `ComplexityEstimator` |
| `05-orchestration.md` | Core graph builder, nodes, extensibility |
| `06-memory.md` | `PostgresMemoryStore`, consolidation, profile |
| `07-container.md` | `Container`, DI wiring, plugin support |
| `08-contacts.md` | `PersonStore`, `ContactChannelStore`, extraction |

### Architecture decisions (`arch/`)

| Spec | Decision |
|------|----------|
| `package-reorg.md` | Monorepo split into ze-core / ze-personal / ze / ze-browser |
| `plugin-agents.md` | ZePlugin ABC, domain agent migration to ze-personal |

## Cross-Cutting Modules

| Module | Package | Purpose |
|--------|---------|---------|
| `ze_core/openrouter/` | `ze-core` | All LLM calls via OpenRouter |
| `ze_core/embeddings.py` | `ze-core` | Shared paraphrase-multilingual-MiniLM-L12-v2 singleton |
| `ze_core/telemetry/` | `ze-core` | Cost tracking, context vars |
| `ze/settings.py` | `ze` | Pydantic BaseSettings, secrets |
| `ze/errors.py` | — | Base exception hierarchy (re-exported via ze_core.errors) |

## Configuration Files

| File | Purpose |
|------|---------|
| `.env` | Secrets — API keys, DB URL, timeouts |
| `config/config.yaml` | Models, contacts settings, proactive schedules |
| `config/persona.yaml` | Persona profiles and dials |

Agent capabilities (permission modes) are declared as class attributes on each
`@agent` class — there is no `capabilities.yaml`.

## Resolved Constraints

- **Single user.** No multi-tenant memory, no user isolation, no session auth beyond
  a static API key (`ZE_API_KEY` in `.env`).
- **All LLM calls via OpenRouter.** No direct Anthropic/OpenAI calls. Web search
  uses `openrouter:web_search` server tool — no separate search API key.
- **Google API auth.** OAuth2 (Calendar + Gmail). Refresh token stored as
  `GOOGLE_REFRESH_TOKEN` Fly.io secret. Access token exchanged at startup and on 401.
- **Mobile interface.** Delivered natively through Telegram. No separate mobile app.
- **Capabilities.** Declared as `Mode` class attributes on `@agent` classes. No
  external YAML file for permission config.
- **Package structure.** Monorepo with `ze-core` (pure infra), `ze-personal` (domain),
  `ze` (application), `ze-browser` (sidecar). See `arch/package-reorg.md`.

## Open Questions

- [x] Phase 3: OAuth2 strategy resolved — Google OAuth2 (Calendar + Gmail).
- [x] Phase 4: workflow agent scoped to APScheduler-based multi-step plan execution.
- [x] Phase 17: ze-browser sidecar uses Playwright; anti-bot stealth handled in sidecar.
- [x] Phase 20: ze-core is pure infrastructure; domain code lives in ze-personal.
