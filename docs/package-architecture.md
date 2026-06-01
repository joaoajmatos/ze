# Ze — Package Architecture

Ze is a monorepo split into four packages with a strict one-way dependency graph.
Understanding the split makes it clear where new code belongs and how the pieces fit.

---

## Packages

```
packages/
├── ze-core/        # Pure infrastructure — no domain knowledge
├── ze-personal/    # Personal-assistant domain layer
├── ze/             # Application — Telegram, Google, agents, API
└── ze-browser/     # Browser sidecar client
```

### Dependency graph

```
ze-browser  ←  no ze deps
ze-core     ←  no ze deps
ze-personal ←  ze-core
ze          ←  ze-core, ze-personal, ze-browser
```

This is a hard rule: `ze-core` never imports from `ze-personal` or `ze`.
`ze-personal` never imports from `ze`. Violations break the abstraction and
make it impossible to reuse or test the infrastructure layer in isolation.

---

## ze-core — Pure Infrastructure

`ze_core` owns every primitive that is not specific to "Ze the personal assistant":

| Module | What it provides |
|--------|-----------------|
| `orchestration/` | LangGraph graph builder, `BaseAgent`, `@agent` decorator, node implementations, `AgentState`, `AgentContext` |
| `routing/` | `EmbeddingRouter`, `ComplexityEstimator`, `RoutingFallback` |
| `memory/` | `PostgresMemoryStore`, `MemoryConsolidator`, types (`UserFact`, `Episode`, `UserProfile`, `MemoryContext`) |
| `capability/` | `CapabilityGate`, `Mode`, `GateDecision`, `PostgresCapabilityOverrideStore` |
| `channels/` | `Channel` ABC, `ChannelRegistry`, `ChannelType`, `Message`, `SentMessage` |
| `interface/` | `AppInterface` ABC, `InputPreprocessor`, validation |
| `openrouter/` | `OpenRouterClient`, streaming, transcription |
| `telemetry/` | `CostTracker`, `CostReconciler`, `PostgresCostStore`, context vars |
| `proactive/` | `ProactiveScheduler`, `ProactiveNotifier`, `ProactiveJob` |
| `progress/` | `ProgressReporter`, locale translations |
| `embeddings.py` | Shared `all-MiniLM-L6-v2` singleton |
| `container.py` | Base `Container` with DI wiring, plugin support, `invoke`/`resume` |
| `plugin.py` | `ZePlugin` ABC |
| `errors.py` | Typed exception hierarchy |

**Rule of thumb:** if you could imagine shipping `ze-core` as a standalone
"AI assistant framework" library and the feature would still make sense — it belongs
in `ze-core`. If it only makes sense for Ze's personal assistant use-case, it
belongs elsewhere.

---

## ze-personal — Domain Layer

`ze_personal` owns all personal-assistant domain logic. It depends on `ze-core`
but knows nothing about Telegram, Google APIs, or HTTP.

| Module | What it provides |
|--------|-----------------|
| `persona/` | `PostgresPersonaStore`, `build_identity_block`, named profiles, dial overrides |
| `contacts/` | `PersonStore`, `ContactChannelStore`, extractors, consolidator, tools |
| `goals/` | `GoalStore` (postgres.py), `GoalPlanner`, `GoalExecutor`, types |
| `workflow/` | `WorkflowStore`, `WorkflowPlanner`, `WorkflowScheduler`, types |
| `agents/goals/` | `GoalAgent` — conversational goal lifecycle |
| `agents/workflow/` | `WorkflowManagerAgent` — conversational workflow management |
| `graph/workflow.py` | Execution nodes wired into the orchestration graph |
| `graph/memory_hooks.py` | Post-memory-write hooks (e.g. contact extraction) |
| `plugin.py` | `PersonalPlugin(ZePlugin)` — wires all of the above into ze-core |

---

## ze — Application

`ze` is the runnable application. It depends on both `ze-core` and `ze-personal`.

| Module | What it provides |
|--------|-----------------|
| `agents/` | Domain agents: research, companion, calendar, email, reminders, prospecting |
| `telegram/` | `ZeBot`, `TelegramAppInterface`, handlers, `ActiveSessionStore` |
| `google/` | Google OAuth2 token management, `GmailChannel`, Calendar API client |
| `api/` | FastAPI app, Telegram webhook router, REST routes |
| `jobs/` | Proactive cron jobs: briefing, insights, calendar sync, contacts, prospecting |
| `reminders/` | `ReminderStore`, `CalendarReminderService`, `CalendarReminderStore` |
| `prospecting/` | `ProspectCampaignStore` and prospecting-specific persistence |
| `container.py` | `ZeContainer` — subclasses `ze_core.Container`, registers `PersonalPlugin` |
| `settings.py` | Pydantic `BaseSettings`, `to_core_settings()` bridge |

---

## ze-browser — Sidecar Client

`ze_browser` is a thin HTTP client for the browser sidecar service (Playwright + FastAPI
running as a separate process). It has no ze dependencies.

| Module | What it provides |
|--------|-----------------|
| `client.py` | `BrowserClient` — `httpx`-based async client |
| `types.py` | `BrowserResult` |
| `errors.py` | `BrowserError` |

The sidecar itself is deployed separately and is never imported by any Python package.

---

## The ZePlugin Extension Point

`ZePlugin` is the seam that lets `ze-personal` (and any future domain package) inject
behaviour into `ze-core` without `ze-core` knowing about it.

```python
class ZePlugin(ABC):
    # Container-level hooks
    def agents(self) -> list[type[BaseAgent]]: ...         # extra agent classes to register
    def jobs(self) -> list[ProactiveJob]: ...               # extra scheduled jobs
    def migrations_path(self) -> Path | None: ...           # package-specific migrations

    # Graph-level hooks (applied at build time)
    def state_extensions(self) -> type | None: ...          # extra AgentState fields (TypedDict)
    def graph_nodes(self) -> dict[str, Callable]: ...       # extra LangGraph nodes
    def graph_edges(self, builder: StateGraph) -> None: ... # wire extra edges
    def configurable_services(self) -> dict[str, Any]: ...  # inject into config["configurable"]
    def agent_module_paths(self) -> list[str]: ...          # modules to import for @agent side effects
```

`PersonalPlugin` (in `ze_personal/plugin.py`) is the only plugin currently registered.
It contributes:

- `identity_builder` — `build_identity_block()` from `ze_personal.persona.identity`.
  Builds the persona + memory context injected into every agent system prompt.
- `memory_hooks` — `[contact_proposal_hook]`. Runs contact extraction after every
  memory write.
- Agent module paths — `ze_personal.agents.goals.agent` and
  `ze_personal.agents.workflow.agent`, so those agents register via `@agent` at
  container startup.

### Adding a new plugin

1. Create a class that inherits `ZePlugin` in your package.
2. Override only the methods you need (all have no-op defaults).
3. Instantiate it in `ze/container.py` and pass it to `ZeContainer`:

```python
from ze_personal.plugin import PersonalPlugin
from mypackage.plugin import MyPlugin

container = ZeContainer(
    settings=settings,
    plugins=[PersonalPlugin(), MyPlugin()],
)
```

Plugins are applied in order. State extension fields and graph nodes from all plugins
are merged before the graph is compiled.

---

## Where does new code go?

| New code | Package |
|----------|---------|
| New infrastructure primitive (router, gate, store type) | `ze-core` |
| New domain concept tied to personal assistant | `ze-personal` |
| New Telegram command or feature | `ze` → `ze/telegram/` |
| New Google integration | `ze` → `ze/google/` |
| New agent (most agents) | `ze` → `ze/agents/<name>/` |
| New agent that needs domain state (goals, workflows) | `ze-personal` → `ze_personal/agents/<name>/` |
| New background job | `ze` → `ze/jobs/` |
| New channel implementation (LinkedIn, WhatsApp) | `ze` → `ze/channels/<name>.py` |
| Headless browser interaction | `ze-browser` |

When in doubt: ask whether the code has a runtime dependency on `ze-personal` or
application config. If yes, it belongs in `ze`. If it depends only on `ze-core`
abstractions, it can live in `ze-personal`.
