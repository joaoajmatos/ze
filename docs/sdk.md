# Ze SDK Reference

`ze-sdk` is the single dependency plugin authors declare. It re-exports every public
symbol from `ze-agents`, `ze-proactive`, `ze-memory`, `ze-onboarding`, `ze-plugin`, and
`ze-data` through a flat, stable surface.
Plugin packages never import `ze-core` directly.

---

## Import map

```python
from ze_sdk import ZePlugin, agent, tool, ToolAccess, BaseAgent, get_logger, Settings, DBPool, NLIClient
from ze_sdk import DataDomain
from ze_sdk.types import AgentContext, AgentResult, ToolCall, AbortToken, Action, Notification
from ze_sdk.proactive import ProactiveJob, proactive_job, ProactiveScheduler, ProactiveNotifier, PushKind, PushOutcome, PushLogStore, PushLogEntry
from ze_sdk.channels import Channel, ChannelType, ChannelHandle, Message, SentMessage, Thread, ThreadMessage, ChannelSendError
from ze_sdk.memory import MemoryContext, Fact, Episode, Procedure, Entity, TaskState, RetrievalRequest, MemoryStore, PostgresMemoryStore, PostgresDreamStore, DreamArtifact, DreamJournalEntry, DreamRun, ArtifactType, ArtifactStatus
from ze_sdk.contribution import Contribution, EvidenceRef, SourceFunction, TargetFace, validate_and_submit, submit_and_detect_collisions
from ze_sdk.api import require_api_key
from ze_sdk.onboarding import OnboardingProvider, OnboardingStep, OnboardingField, OnboardingSeed, OnboardingResult
from ze_sdk.errors import ZeError, AgentError, AgentAbortedError, AgentConfigError, ChannelSendError
```

---

## `ze_sdk` — core authoring API

| Symbol | What it is |
|--------|-----------|
| `ZePlugin` | Abstract base class for domain extensions. Override only the hooks you need.|
| `agent` | Class decorator that registers a `BaseAgent` subclass in the global `AgentRegistry`. |
| `tool` | Function decorator that registers an async function as a callable tool. |
| `ToolAccess` | Enum — `READ` or `WRITE`. A `WRITE` tool that is irreversible asks first by default. |
| `ToolReversibility` | Enum — `REVERSIBLE` or `IRREVERSIBLE`. Required on every `WRITE` tool; see [Tool reversibility](#tool-reversibility). |
| `BaseAgent` | Abstract base class all agents inherit. Provides `agentic_loop`, `call_tool`, `emit`, and `_build_system_prompt`. |
| `get_logger` | Structured logger factory. Always call as `get_logger(__name__)`. |
| `Settings` | Settings dataclass bridge. Agents receive this via DI — never construct it yourself. |
| `DBPool` | Structural `Protocol` for asyncpg connection pools. Use as a type hint in `__init__`. |
| `NLIClient` | `Protocol` for local NLI cross-encoder inference — entailment, contradiction, grounding. |
| `DataDomain` | Descriptor for export/import/delete ownership. Plugins return these via `ZePlugin.data_domains()`. |

---

## `NLIClient`

Local cross-encoder (`cross-encoder/nli-deberta-v3-small`) for semantic comparison
without an LLM call. Satisfied by `LocalNLIClient` in production; mock with
`AsyncMock` in tests.

```python
from ze_sdk import NLIClient

class MyService:
    def __init__(self, nli_client: NLIClient) -> None:
        self._nli = nli_client

    async def check(self, premise: str, hypothesis: str) -> bool:
        if not self._nli.pair_is_scorable(premise, hypothesis):
            return False
        scores = await self._nli.scores([(premise, hypothesis)])
        return bool(scores[0] and scores[0]["entailment"] >= 0.70)
```

| Method | Description |
|--------|-------------|
| `scores(pairs)` | Batch score `(premise, hypothesis)` pairs. Returns `entailment`, `contradiction`, `neutral` probs, or `None` for non-Latin pairs. |
| `grounding_score(hypothesis, evidence_texts)` | Max entailment of hypothesis against each evidence string. |
| `pair_is_scorable(premise, hypothesis)` | Fast Latin-script gate before scoring. |

**Shared agent tools** (import `ze_agents.nli_tools` in `agent_module_paths()`):

| Tool | Purpose |
|------|---------|
| `nli_check_entailment` | Compare two strings; returns entailment/contradiction scores. |
| `nli_grounding` | Score how well a claim is supported by a list of evidence texts. |

Pass `deps={"nli_client": self._nli}` into `agentic_loop()` so tools receive the client.

---

## `ze_sdk.types` — runtime types

### `AgentContext`

Passed to every `BaseAgent.run()` call. Contains everything the agent needs for one turn.

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | `str` | Unique conversation/graph thread ID. |
| `prompt` | `str` | The user's message for this turn. |
| `memory` | `MemoryContext \| None` | Retrieved memory for this turn. |
| `contacts` | `ContactsContext \| None` | Retrieved contacts for this turn. |
| `tool_calls` | `list[ToolCall]` | Tool calls accumulated so far in this turn. |
| `messages` | `list[dict]` | Conversation history (OpenAI message format). |
| `persona` | `dict` | Active persona dials. |
| `model` | `str \| None` | Override model string. Falls back to agent's class attribute. |
| `reporter` | `ProgressReporter \| None` | Emit localized progress messages via `self.emit(ctx, key)`. Keys are defined in each plugin's `locales/` YAML files. See [adding-an-agent.md](adding-an-agent.md#progress-messages). |
| `extensions` | `dict[str, ...]` | Arbitrary msgpack-serializable data (e.g. `goal_id`). |

Fields `identity_builder`, `abort_token`, and `memory_store` are runtime-only — never checkpoint a context where they are set.

### `AgentResult`

Returned from `BaseAgent.run()`.

| Field | Type | Description |
|-------|------|-------------|
| `agent` | `str` | Agent name (matches `BaseAgent.name`). |
| `response` | `str` | Final text response to show the user. |
| `tool_calls` | `list[ToolCall]` | All tool calls made during this turn. |
| `tokens_used` | `int` | Token count for telemetry. |
| `contact_proposals` | `list` | Proposed contacts for consolidation. |
| `extensions` | `dict[str, Any]` | Arbitrary data forwarded to graph state. |

There is no `memory_proposals` field. Companion persists explicit facts with `remember_fact` / `forget_fact`, not by stuffing the result object.

### `ToolCall`

Structured record of a single tool invocation.

| Field | Type | Description |
|-------|------|-------------|
| `tool_name` | `str` | Registered tool name. |
| `args` | `dict` | Arguments passed to the tool. |
| `result` | `Any` | Return value, or `None` on failure. |
| `duration_ms` | `int` | Wall-clock execution time. |
| `success` | `bool` | Whether the tool ran without exception. |
| `error` | `str \| None` | Error message if `success=False`. |
| `parent_call_id` | `str \| None` | For a call a script made, or a proposed write: the `run_tool_script` call that made it. |
| `inner_calls` | `list[ToolCall]` | For a `run_tool_script` call: the reads the script made, in order. |
| `script` | `dict \| None` | For a `run_tool_script` call: the step summary (source, outcome, limit, source hash, procedure id). |

### `AskDecision`

Returned by an `ask_check` function. It tells Ze what to do with one call.

| Value | Meaning |
|-------|---------|
| `RUN` | Run the call without asking. |
| `ASK(reason)` | Park the call and ask the user. `reason` is optional. |
| `REFUSE(message)` | Refuse the call. Nothing is parked, and the model gets `message`. |

### `AbortToken`

Async signal that cancels a running `agentic_loop` between iterations.

```python
token = AbortToken()
token.abort(reason="user cancelled")   # signals the loop to stop
token.is_set                            # True after abort()
```

### `Action` and `Notification`

Returned from `AppInterface` to the transport layer. Plugin authors rarely construct these directly — they come from `BaseAgent.run()` returning an `AgentResult`, which the graph nodes convert to frames.

---

## `BaseAgent` — abstract base class

All agents subclass `BaseAgent` and decorate the class with `@agent`.

### Class attributes

```python
@agent
class MyAgent(BaseAgent):
    name         = "my_agent"           # unique, snake_case — used for routing
    description  = "What this agent does."  # embedded for cosine-similarity routing
    model        = "anthropic/claude-sonnet-4-5"
    model_simple = None                 # optional lighter model; used only for turns System One judges light (complexity surface, on in the shipped config)
    vision_capable = False              # set True to receive image data in ctx
    timeout      = 30                   # seconds
    tools        = ["tool_a", "tool_b"] # @tool-registered names
```

All attributes except `name` have defaults — only override what differs.

### Abstract method

```python
@abstractmethod
async def run(self, ctx: AgentContext) -> AgentResult: ...
```

### Instance helpers

#### `self._build_system_prompt(instructions, ctx, **extra) -> str`

Builds the system prompt. Order: current datetime, shared memory constitution, persona traits, then your agent instructions (job), then retrieved biography from `_format_memory` (origin, confidence, recency). Always call this instead of concatenating manually. Do not treat the biography as a recitation duty.

```python
system = self._build_system_prompt(_AGENT_INSTRUCTIONS, ctx)
```

Pass `**extra` to use `.format()` placeholders in `_AGENT_INSTRUCTIONS`.

#### `await self.agentic_loop(ctx, client, messages, system, deps=None, tool_names=None, max_iterations=6, max_tokens=2000) -> tuple[str, list[ToolCall]]`

Drives an LLM ReAct loop: the model picks tools, ze dispatches them through `call_tool`, appends results to `messages`, and repeats until the model produces a text response.

- `client` — the `LLMClient` injected via `__init__`.
- `messages` — conversation history. Pass `ctx.messages` for full history.
- `system` — built by `_build_system_prompt`.
- `deps` — internal dependencies the LLM cannot provide (e.g. `{"client": self._client}`). Ze merges them into tool kwargs automatically.
- `tool_names` — defaults to `self.tools`.
- Returns `(final_response_text, list_of_all_tool_calls)`.

#### `await self.call_tool(name, ctx, **kwargs) -> ToolCall`

Executes a single registered tool, with hook dispatch.

- An asks-first `WRITE` tool does not run. The call parks, and the loop stops at it. See [Write confirmation](architecture.md#write-confirmation).
- A call to an asks-first tool outside `agentic_loop` or `delegate_to_agent` raises `AgentConfigError`.
- Pass all tool dependencies (clients, settings) as keyword arguments.

#### `await self.emit(ctx, key, **kwargs)`

Sends a progress message to the client using a locale translation key. No-op when the agent has no reporter attached (e.g. in tests).

#### `self._model(ctx) -> str`

Returns the active model string — respects `ctx.model` overrides and falls back to `self.model`.

### Lifecycle hooks

```python
async def startup(self) -> None:
    """Called once after DI wiring. Use for connection warmup."""

async def shutdown(self) -> None:
    """Called during app shutdown. Use for cleanup."""
```

---

## `@agent` decorator

```python
from ze_sdk import agent

@agent
class MyAgent(BaseAgent): ...
```

Registers the class in the global `AgentRegistry` when the module is imported. The `bootstrap.py` entry point imports all modules listed in `ZePlugin.agent_module_paths()` to trigger registration. There is nothing else to call — the decorator is the entire registration.

---

## `@tool` decorator and `ToolAccess`

```python
from ze_sdk import tool, ToolAccess

@tool(access=ToolAccess.READ, description="Fetch data from the database.")
async def get_record(id: str, db: DBPool) -> str:
    async with db.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM records WHERE id = $1", id)
        return str(row)
```

### Asks first

An irreversible `WRITE` tool asks the user first by default. You pass no argument for this.

| Argument | Meaning |
|---|---|
| `asks_first=False` | The tool runs without asking. Requires `reversibility=ToolReversibility.IRREVERSIBLE` and `no_ask_reason`. |
| `no_ask_reason` | One sentence that says why no confirmation is needed. Allowed only with `asks_first=False`. |
| `editable_field` | The name of a parameter the user may edit in the confirmation, for example `"body"`. |
| `summarize` | A function that returns a short summary for the confirmation. It gets the call's arguments and injected dependencies and may be `async`. If it fails or returns nothing, the confirmation lists the arguments. |
| `ask_check` | A function `(args, ctx) -> AskDecision` that decides per call. It must be cheap and free of side effects. |

The function body runs only after the user approves that exact call. A tool body never
opens a confirmation itself.

### Rules

- Tools must be `async def`.
- All parameters the LLM cannot infer must be typed — they are injected via `deps` in `agentic_loop` or passed explicitly via `call_tool(**kwargs)`.
- `ToolAccess.READ` — no external side effects. Runs without asking.
- `ToolAccess.WRITE` — creates, modifies, deletes, or sends. An irreversible write asks first unless it declares `asks_first=False` with a `no_ask_reason`. Must declare `reversibility`.

### Tool reversibility

`@tool` takes four more arguments for `WRITE` tools:

| Argument | Meaning |
|---|---|
| `reversibility` | `ToolReversibility.REVERSIBLE` or `ToolReversibility.IRREVERSIBLE`. Required for `WRITE`. There is no default. |
| `undo_tool` | Name of the registered `WRITE` tool that undoes this one. Required for `REVERSIBLE`, not allowed for `IRREVERSIBLE`. |
| `undo_note` | One line that says what the undo cannot restore. Required for `REVERSIBLE`. |
| `effect_phrase` | Past-tense phrase such as `"set a reminder"`. Ze shows it in the Retry reason. |

```python
from ze_sdk import tool, ToolAccess, ToolReversibility

@tool(
    access=ToolAccess.WRITE,
    description="Set a reminder.",
    reversibility=ToolReversibility.REVERSIBLE,
    undo_tool="cancel_reminder",
    undo_note="Does not recall a notification that already showed",
    effect_phrase="set a reminder",
)
async def set_reminder(label: str, fire_at: str, store: ReminderStore) -> dict: ...
```

A `WRITE` tool without `reversibility`, a `REVERSIBLE` tool without `undo_tool` or
`undo_note`, an `IRREVERSIBLE` tool with either, or a `READ` tool with any of the four
raises `AgentConfigError` when the module imports. At startup Ze checks that every
`undo_tool` names a registered `WRITE` tool other than the tool itself.

The declaration decides whether Retry is available. Retry is unavailable after any
`WRITE` tool ran, so the declaration also shapes the reason text.

### Tool parameters

| Parameters | Provided by |
|------------|-------------|
| Simple scalar types (`str`, `int`, `bool`) | LLM |
| Clients, stores, settings | `deps` dict in `agentic_loop` or explicit kwargs in `call_tool` |

### Tool scripts: `produces_ui` and `egress`

Tool scripts are a harness capability. You do not opt an agent in. Every agent with a data
read tool gets `run_tool_script`, and the script stub holds that agent's data read tools.
Two flags keep a tool out of the stub:

| Argument | Set it when |
|---|---|
| `produces_ui=True` | The tool's effect is drawing on screen, such as a render tool or a `show_*` compose tool. A UI tool is never a data read. |
| `egress=True` | A `READ` tool reaches a caller-chosen URL or host, such as `browser_extract`, or fetches from the network on every call, such as `refresh_news`. A script has no network when the sandbox is isolated, so Ze never gives it such a tool. |

A `READ` tool with a URL-like parameter (`url`, `uri`, `link`, `host`, `endpoint`, `domain`)
must set `egress=True` or carry an explicit exemption with a reason. Otherwise the registry
sweep fails.

In a script, each stub tool is a function that takes keyword arguments and returns the
tool's JSON result: dicts, lists or strings. A result that JSON cannot encode, such as a
dataclass or a `Decimal`, arrives as its `str()`. A `datetime` or `date` arrives as an ISO
string. Numbers, booleans and `None` arrive unchanged. Scripts reach a `WRITE` tool only through
`propose(tool, **args)` inside `finish(...)`. Calling a write tool directly from a script is
refused with `writes_must_be_proposed`.

### OpenRouter web search

Declare `"openrouter:web_search"` in `tools` to let the model trigger a web search. No Python tool function is needed — OpenRouter executes it and the result appears in the conversation automatically.

```python
tools = ["openrouter:web_search", "my_tool"]
```

---

## `ZePlugin` — extension point

```python
from ze_sdk import ZePlugin

class MyPlugin(ZePlugin):
    ...
```

Override only the hooks your plugin needs. All methods have no-op defaults.

### Container-level hooks

| Method | Signature | Purpose |
|--------|-----------|---------|
| `agents()` | `-> list[type[BaseAgent]]` | Agents to register (rarely used — prefer `agent_module_paths`). |
| `jobs()` | `-> list[Any]` | Proactive job instances to register. |
| `onboarding()` | `-> OnboardingProvider \| None` | Onboarding provider for first-run setup. |
| `migrations_path()` | `-> Path \| None` | `classmethod`. Path to the package's `migrations/` directory (with `env.py` and `versions/`). |
| `agent_module_paths()` | `-> list[str]` | Module paths imported at bootstrap to trigger `@agent`/`@tool` registration. List tools module before agent module. |
| `agent_deps(accumulated)` | `-> dict` | Extra types the plugin's agents need injected, merged into the bootstrap dependency map. |
| `integration_types()` | `classmethod -> list[type]` | Integration credential types the plugin needs (for example `Trading212Client`). |
| `signal_sources()` | `-> list[SignalSource]` | Signal sources fed into the admission and correlation pipeline. Duplicate `source_key` values raise `AgentConfigError`. |
| `webhook_handlers()` | `-> list` | `WebhookHandler` instances for inbound webhooks. |
| `channels()` | `-> list[Any]` | Communication channel instances, collected into the `ChannelRegistry`. |
| `data_domains()` | `-> list[DataDomain]` | Export, import, and delete contract for the plugin's tables. |
| `ingestion_fetchers()` / `ingestion_extractors()` | `-> list` | Custom content fetchers and extractors for `ze-ingestion`. |
| `ui_contributions()` | `-> list` | Modules, Ask presets and settings sections for ze-web, served at `GET /api/v0/ui/manifest`. Plugins add no pages. See [Adding UI to a plugin](extending-ze.md#adding-ui-to-a-plugin). |
| `rest_routes()` | `-> list` | FastAPI routers the plugin owns. |
| `rest_stores()` | `-> dict[str, Any]` | Named stores that REST routes can reach. |
| `screen_resolvers()` | `-> list[ScreenResolver]` | Readers that turn a screen ref (`kind`, `id`) into a short line for the screen note. One resolver per `kind`; a duplicate `kind` fails at startup. See [Screen resolvers](#screen-resolvers). |
| `seed_domains()` | `-> list` | Dev seed fixtures for `ze-seed`. |
| `bundled_skill_paths()` | `-> list[str]` | Filesystem paths to bundled `SKILL.md` files. Registered at startup as `source=bundled`, `status=active`. See [skills.md](skills.md#bundled-skills). |

### Graph-level hooks

| Method | Signature | Purpose |
|--------|-----------|---------|
| `state_extensions()` | `-> type \| None` | A plain `TypedDict` (`total=False`) whose fields are merged into `AgentState`. Do not subclass `AgentState`; the engine adds it. |
| `checkpoint_serde_modules()` | `-> tuple[str, ...]` | `types.py` module paths scanned for checkpoint-serializable dataclasses/enums. |
| `memory_policies()` | `-> dict[str, Any]` | Agent name → retrieval policy for this plugin's agents. |
| `pre_route_node()` | `-> Callable \| None` | An async graph node inserted between preprocess and embed_route. |
| `graph_nodes()` | `-> dict[str, Callable]` | Additional LangGraph nodes keyed by node name. Write them async: the turn timer calls a sync node inline on the event loop. |
| `graph_edges(builder)` | `-> None` | Wire plugin nodes into the graph at build time. |
| `configurable_services()` | `-> dict[str, Any]` | Services injected into `config["configurable"]` every turn. |

### Lifecycle hooks

| Method | Signature | Purpose |
|--------|-----------|---------|
| `startup(container)` | `async -> None` | Called once after the container is fully built. Use for DB connections, credential refresh, scheduler start. |
| `shutdown()` | `async -> None` | Called during app shutdown in reverse startup order. |

### Proactive job registration

```python
def register_proactive_jobs(self, scheduler, settings, *, consolidation_enabled=True) -> None:
    scheduler.register(my_job, cron="0 8 * * *")
```

`ze-api` calls this hook while it registers proactive jobs (`compose.py`). `ProactiveScheduler.register(job, cron)` takes a job with a `job_id` and a `run()` method.

---

## `ze_sdk.onboarding` — setup providers

| Symbol | Description |
|--------|-------------|
| `OnboardingProvider` | Protocol returned by `ZePlugin.onboarding()`. Defines `steps()` and `handle_submission()`. |
| `OnboardingStep` | One setup step, owned by a plugin and rendered by the runtime. |
| `OnboardingField` | A field inside a form step: text, textarea, select, multiselect, boolean, chips, etc. |
| `OnboardingChoice` | A choice/card option for non-form steps. |
| `OnboardingSubmission` | Structured values submitted by the app for a step. |
| `OnboardingSeed` | A typed proposed write: profile facet, memory fact, plugin setting, contact, etc. |
| `OnboardingResult` | Provider response containing seeds and optional follow-up steps. |

Providers should only describe setup needs and return seeds. They must not import
`ze_api`, write directly to global memory, or own the global flow. The runtime reviews
durable seeds before applying them through deployment adapters. See
[onboarding.md](onboarding.md) for the end-to-end flow.

---

## `ze_sdk.proactive` — job scheduling

| Symbol | Description |
|--------|-------------|
| `ProactiveJob` | Protocol. Implement `run(settings, notifier) -> None` and set `job_id: str`, `schedule: str`. |
| `proactive_job` | Class decorator that marks a class as a proactive job and registers it. |
| `ProactiveScheduler` | APScheduler wrapper. Call `add_cron_job(job, cron=...)` inside `register_proactive_jobs`. |
| `ProactiveNotifier` | The one proactive send path. Call `notify(kind, title, body, ...)`; the interruption governor decides delivery. |
| `PushKind` | A declared kind of push: event type, class (`requested`/`accountability`/`discretionary`), urgency (`low`/`normal`/`high`), source. |
| `PushOutcome` | What the governor did with a push: `delivered`, `held`, `suppressed_budget`, `duplicate`, `deduped`, `failed`. |
| `PushLogStore` | Delivery audit log. Persists which notifications have been sent. |
| `PushLogEntry` | Dataclass for a single log entry. |

---

## `ze_sdk.channels` — channel abstraction

| Symbol | Description |
|--------|-------------|
| `Channel` | ABC for message channels (email, SMS, etc.). Override `send`, `receive`, `list_threads`. |
| `ChannelType` | Enum — `EMAIL`, etc. |
| `ChannelHandle` | A resolved contact handle for a channel (address + type). |
| `Message` | Inbound or draft message. |
| `SentMessage` | Confirmation of a sent message with provider message ID. |
| `Thread` | Conversation thread in a channel. |
| `ThreadMessage` | Single message within a thread. |
| `ChannelSendError` | Raised when a channel `send()` fails. |

---

## `ze_sdk.memory` — memory types

Plugin agents rarely read memory directly — `ctx.memory` is pre-populated. Use these types for type hints and for direct store access in proactive jobs.

| Symbol | Description |
|--------|-------------|
| `MemoryContext` | Retrieval result: `facts`, `episodes`, `procedures`, `entities`, `task_state`, `profile`. |
| `Fact` | A subject-predicate-value triple stored persistently. |
| `CommitmentChoice` | Enum of the labels the conversation commitment intake answers: `reminder`, `loop`, `goal`, `waiting_on`, `fact`, `forget`, `ingest`, `clarify`, `none`. |
| `Episode` | A summarised conversation episode. |
| `Procedure` | A user-taught step-by-step procedure. |
| `Entity` | A named entity extracted from conversations. |
| `EntityRef` | A reference to an entity, used on `Signal`. |
| `Signal` | A cross-plugin observation emitted by a `SignalSource`. |
| `SignalSource` | Protocol a plugin implements to emit signals. |
| `TaskState` | Current execution state for a running task/goal. |
| `RetrievalRequest` | Parameters for a `MemoryStore.retrieve()` call. |
| `MemoryStore` | Protocol for memory stores. |
| `PostgresMemoryStore` | Default implementation backed by asyncpg + pgvector. |
| `PostgresDreamStore` | Dream pipeline store — journal entries, artifact CRUD, run management. Used by `BriefingJob` (read-only) and the dream REST routes. |
| `DreamArtifact` | A staged synthetic output before/after promotion. |
| `DreamJournalEntry` | Per-run summary surfaced in the morning briefing. |
| `DreamRun` | Metadata for one nightly dream job execution. |
| `ArtifactType` | Enum: `synthesized_insight`, `synthesized_procedure`, `hindsight_fact`, `plan_stress_test`, `schema_candidate`, `policy_candidate`. |
| `ArtifactStatus` | Enum: `pending`, `promoted`, `rejected`, `needs_review`, `revised`, `rolled_back`. |
| `CompanionPolicy`, `ResearchPolicy`, `GoalsPolicy`, `WorkflowPolicy`, `PlannerPolicy`, `CalendarPolicy`, `RemindersPolicy`, `EmailPolicy`, `ProspectingPolicy` | Memory read policies. Return them from `ZePlugin.memory_policies()`. |
| `build_admission_gate` | Builds the signal admission gate from the `correlation.salience` config block. Pass the result to a job that submits signals. |
| `extract_facts`, `fact_extraction_model` | Run the fact extractor on text. Submit the result through `submit_perception_facts`. |
| `WORKS_ON`, `COLLABORATES_WITH` | Graph predicates for social-cognition edges. |
| `Relationship`, `GraphStore` | Graph edge type and the store protocol for reading and writing edges. |

---

## `ze_sdk.contribution` — contribution seam

Plugins that write facts, action records, or other claims go through the contribution seam. See `specs/arch/contribution-seam.md`.

| Symbol | Description |
|--------|-------------|
| `Contribution` | A typed proposal for a write. |
| `EvidenceRef` | A pointer to the evidence behind a contribution. |
| `SourceFunction`, `TargetFace` | The producing function and the target store of a contribution. |
| `validate_and_submit` | Validates a contribution and submits it. |
| `submit_and_detect_collisions` | `validate_and_submit` plus collision logging. |
| `ActionRecorder`, `ActionRecordStore`, `safe_record_action` | Record actions in the action ledger. |

---

## `ze_sdk.api` — REST helpers

| Symbol | Description |
|--------|-------------|
| `require_api_key` | FastAPI dependency that checks the bearer token. Use it on plugin REST routes. |

---

## `ze_sdk.errors` — error hierarchy

Always raise a typed `ZeError` subclass. Never raise bare `Exception` or `ValueError`.

| Error class | When to raise |
|-------------|--------------|
| `ZeError` | Base class. Do not raise directly. |
| `AgentError` | Unrecoverable agent-level failure (unexpected LLM response, missing result). |
| `AgentAbortedError` | Agent loop was cancelled via `AbortToken`. |
| `AgentConfigError` | Misconfiguration detected at startup (missing type hints, unregistered tool). |
| `ChannelSendError` | Channel `send()` failed. |

Import from `ze_sdk.errors`:

```python
from ze_sdk.errors import AgentError
```

---

## `DBPool` protocol

```python
from ze_sdk import DBPool

class MyStore:
    def __init__(self, pool: DBPool) -> None:
        self._pool = pool

    async def get(self, id: str) -> dict:
        async with self._pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM my_table WHERE id = $1", id)
```

`DBPool` is a structural Protocol satisfied by any asyncpg `Pool`. Use it as a type hint — the DI container resolves it by type at startup.

## Screen resolvers

The web app tells Ze what the user is looking at as a list of refs (`{kind, id}`). A plugin that owns a record the user can look at registers a resolver for its kinds, so "this" can mean that record.

```python
from ze_sdk.screen import (
    ResolveContext, ScreenLine, ScreenPosture, ScreenRef, ScreenResolver,
    as_utc, parse_uuid, resolve_each, sanitize_text,
)

class ReminderScreenResolver:
    kinds = frozenset({"reminder"})

    def __init__(self, reminder_store) -> None:
        self._reminders = reminder_store

    async def resolve(self, refs: list[ScreenRef], ctx: ResolveContext) -> list[ScreenLine]:
        return await resolve_each(refs, lambda ref: self._load(ref, ctx))

    async def _load(self, ref, ctx) -> ScreenLine | None:
        reminder = await self._reminders.get(parse_uuid(ref.id))
        if reminder is None:
            return None  # becomes a "missing" line
        return ScreenLine(
            ref=ref,
            label=sanitize_text(reminder.label, 120),
            summary="fires " + as_utc(reminder.fire_at).strftime("%Y-%m-%d %H:%M UTC"),
            posture=ScreenPosture(source="reminder"),
        )

class MyPlugin(ZePlugin):
    def screen_resolvers(self) -> list[ScreenResolver]:
        return [ReminderScreenResolver(self._reminders)]
```

A resolver reads one record per ref and returns a label, a summary and the record's posture. `resolve_each` reads the refs in parallel and turns a `None` into a `missing` line and an exception into a `failed` one. Wrap every piece of user text in `sanitize_text`: it collapses newlines and defuses brackets and forged `"this" =` bindings. Each resolver gets 300 ms and the whole step 800 ms, so read one row and no more. Two resolvers cannot claim the same kind; Ze fails at startup. The note is a hint. It never replaces a tool read.
