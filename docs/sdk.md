# Ze SDK Reference

`ze-sdk` is the single dependency plugin authors declare. It re-exports the public
symbols of `ze-agents`, `ze-automation`, `ze-collision`, `ze-communication`,
`ze-correlation`, `ze-data`, `ze-logging`, `ze-memory`, `ze-onboarding`, `ze-plugin`, and
`ze-proactive` through a flat, stable surface.
Plugin packages never import `ze-core` directly.

---

## Import map

```python
from ze_sdk import ZePlugin, agent, tool, ToolAccess, ToolReversibility, BaseAgent, get_logger, Settings, DBPool, NLIClient
from ze_sdk import DataDomain
from ze_sdk.types import AgentContext, AgentResult, ToolCall, AbortToken, AskDecision, Action, Notification
from ze_sdk.proactive import ProactiveJob, proactive_job, ProactiveScheduler, ProactiveNotifier, PushKind, PushOutcome, PushLogStore, PushLogEntry
from ze_sdk.channels import Channel, InboundChannel, ChannelType, ChannelHandle, Message, SentMessage, Thread, ThreadMessage, ChannelSendError
from ze_sdk.memory import MemoryContext, Fact, Episode, Procedure, Entity, TaskState, RetrievalRequest, MemoryStore, PostgresMemoryStore, PostgresDreamStore, DreamArtifact, DreamJournalEntry, DreamRun, ArtifactType, ArtifactStatus
from ze_sdk.contribution import Contribution, EvidenceRef, SourceFunction, TargetFace, validate_and_submit, submit_and_detect_collisions
from ze_sdk.automation import Goal, GoalStore, Workflow, WorkflowStore
from ze_sdk.correlation import Hypothesis, HypothesisStore
from ze_sdk.screen import ScreenResolver, ScreenLine, ScreenRef
from ze_sdk.ui import UiContribution, ModuleSubject, ModuleResult
from ze_sdk.api import require_api_key
from ze_sdk.onboarding import OnboardingProvider, OnboardingStep, OnboardingField, OnboardingSeed, OnboardingResult
from ze_sdk.errors import ZeCoreError, AgentError, AgentAbortedError, AgentConfigError, ChannelSendError
```

---

## `ze_sdk` — core authoring API

| Symbol | What it is |
|--------|-----------|
| `ZePlugin` | Abstract base class for domain extensions. Override only the hooks you need.|
| `agent` | Class decorator that registers a `BaseAgent` subclass in the global `AgentRegistry`. |
| `tool` | Function decorator that registers an async function as a callable tool. |
| `ToolAccess` | Enum — `READ` or `WRITE`. A `WRITE` tool that is irreversible asks first by default. |
| `Injected` | Type marker for a tool parameter that Ze supplies and the model never sees: `session_id: Injected[str \| None] = None`. |
| `AskDecision` | Result of an `ask_check`: run, ask or refuse. Also in `ze_sdk.types`. |
| `undo_payload` | Builds the per-call `undo` dict that a `REVERSIBLE` tool returns. Values must be scalars or lists of scalars. |
| `ToolReversibility` | Enum — `REVERSIBLE` or `IRREVERSIBLE`. Required on every `WRITE` tool; see [Tool reversibility](#tool-reversibility). |
| `BaseAgent` | Abstract base class all agents inherit. Provides `agentic_loop`, `call_tool`, `emit`, and `_build_system_prompt`. |
| `get_logger` | Structured logger factory. Always call as `get_logger(__name__)`. |
| `Settings` | Settings dataclass bridge. Agents receive this via DI — never construct it yourself. |
| `parse_llm_json` | Parses a model's JSON reply (fences, surrounding prose). Raises `LLMJsonParseError`. Never call `json.loads` on a model reply. |
| `hold_token_sink`, `publish_honest_reply` | Hold an agent's streamed tokens, then publish the reply after the honesty gate checked its memory claims against the tool calls. |
| `SystemOneClient` | `Protocol` for typed judgments (`noul`, `choice`, `score`). See [system-one.md](system-one.md). |
| `WebhookHandler` | `Protocol` for a plugin that receives non-channel webhook events. Return instances from `ZePlugin.webhook_handlers()`. |
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
| `grounding_score(hypothesis, evidence_texts)` | Mean entailment probability of the hypothesis across the evidence strings. |
| `pair_is_scorable(premise, hypothesis)` | Fast Latin-script gate before scoring. |

The container resolves an `NLIClient` constructor parameter by type. Ze has no shared NLI
agent tools: call the client from your own code.

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
| `timezone` | `str` | IANA timezone name for the current-time line in the prompt. Defaults to `UTC`; the graph sets it from the configured timezone (`timezone` in `config.yaml`, then `TIMEZONE`). |
| `sources` | `list[Source]` | Web citations collected while the agent runs. |
| `write_gate` | `WriteGateState` | Write-confirmation and Retry state that the write gates read: the saved loop to resume, the decisions, the pre-approved calls and the round. Run-local. |
| `conductor` | `ConductorState` | The conductor's state for this run: the hint, this run's ledger, the shared delegate tally and the deadline. Run-local. |
| `procedure_invocation` | `ProcedureInvocation \| None` | The procedure this run invoked. Its `tool_names` only narrow the agent's tools. |

The context also carries runtime-only fields: `identity_builder`, `abort_token`, `memory_store`, `embed_fn`, `token_sink`, `tool_sink`, `script_runner`, and the screen, recap, skill, procedure and write-confirmation notes the graph sets. Never checkpoint a context where they are set.

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
| `sources` | `list[Source]` | Web citations the reply drew on. |

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
| `gate` | `str` | Write-confirmation outcome: `none`, `approved`, `pre_approved`, `parked`, `denied`, `refused`, `refused_over_cap`, `expired` or `duplicate`. |
| `parked`, `child_loop`, `approval` | | Park state of an asks-first call and the approval record of an approved one. |
| `agent` | `str \| None` | Name of the agent that made the call. |
| `undo` | `dict \| None` | The `undo_payload` a reversible call returned. |
| `call_id`, `started_at` | `str`, `float \| None` | Id that joins a live tool row to its committed row, and the monotonic start time. |
| `parent_call_id` | `str \| None` | For a call a script made, or a proposed write: the `run_tool_script` call that made it. |
| `inner_calls` | `list[ToolCall]` | For a `run_tool_script` call: the reads the script made, in order. |
| `script` | `dict \| None` | For a `run_tool_script` call: the step summary (source, outcome, limit, source hash, procedure id). |

### `AskDecision`

Returned by an `ask_check` function. It tells Ze what to do with one call.

| Constructor | Meaning |
|-------|---------|
| `AskDecision.run()` | Run the call without asking. |
| `AskDecision.ask(reason="")` | Park the call and ask the user. `reason` is optional. |
| `AskDecision.refuse(message, result=None)` | Refuse the call. Nothing is parked, and the model gets `message` (and `result`, if given). |

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
    timeout      = 30                   # seconds
    tools        = ["tool_a", "tool_b"] # @tool-registered names
```

`name` and `description` are required. The other attributes have defaults (`display_name`,
`routing_criteria`, `enabled`, `system_prompt` and the shipped default model and timeout), so
override only what differs. `routing_criteria` is the text the routing Choice reads; it falls
back to `description`.

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

#### `await self.agentic_loop(ctx, client, messages, system, deps=None, tool_names=None, max_iterations=6, max_history_tokens=None, max_tokens=2000) -> tuple[str, list[ToolCall]]`

Drives an LLM ReAct loop: the model picks tools, ze dispatches them through `call_tool`, appends results to `messages`, and repeats until the model produces a text response.

- `client` — the `LLMClient` injected via `__init__`.
- `messages` — conversation history. Pass `ctx.messages` for full history.
- `system` — built by `_build_system_prompt`.
- `deps` — internal dependencies the LLM cannot provide (e.g. `{"client": self._client}`). Ze merges them into tool kwargs automatically.
- `tool_names` — defaults to `self.tools`.
- Returns `(final_response_text, list_of_all_tool_calls)`.
- Raises `LoopParked` after a response whose asks-first calls were parked. The delegate or subtask boundary catches it.

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

Registers the class in the agent registry (`ze_agents/registry.py`) when the module is imported. `bootstrap_agents` (`ze_agents/bootstrap.py`) imports all modules listed in `ZePlugin.agent_module_paths()` to trigger registration. There is nothing else to call — the decorator is the entire registration.

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
| `constraint_gate` | Opt in to the constraint veto: the harness hooks' `check_call` runs before the tool, and the strictest decision wins (refuse over ask). |
| `ui_action`, `done_phrase` | Let a screen button name this `WRITE` tool (`ToolAction`). `done_phrase` is the line shown after it ran. Not allowed on `READ` tools. |

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

Override only the hooks your plugin needs. All methods have no-op defaults. Set the class attribute `depends_on` (a tuple of plugin names) to start after other plugins.

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
| `locale_data(locale)` | `-> dict` | Progress-message translations. The default reads `locales/{locale}.yaml` in the plugin package. |
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
| `state_extensions()` | `-> type \| None` | A plain `TypedDict` (`total=False`) whose fields are merged into `AgentState`. Every field needs a lifetime marker from `ze_sdk.types` (`Turn`, `Input`, `Thread` or `Run`). A field with no marker raises `UndeclaredLifetimeError`, and graph build fails at startup. Do not subclass `AgentState`; the engine adds it. See [Lifetime markers](#lifetime-markers). |
| `checkpoint_serde_modules()` | `-> tuple[str, ...]` | `types.py` module paths scanned for checkpoint-serializable dataclasses/enums. |
| `memory_policies()` | `-> dict[str, Any]` | Agent name → retrieval policy for this plugin's agents. |
| `pre_route_node()` | `-> Callable \| None` | An async graph node inserted between preprocess and embed_route. |
| `graph_nodes()` | `-> dict[str, Callable]` | Additional LangGraph nodes keyed by node name. Write them async: the turn timer calls a sync node inline on the event loop. |
| `graph_edges(builder)` | `-> None` | Wire plugin nodes into the graph at build time. |
| `configurable_services()` | `-> dict[str, Any]` | Services injected into `config["configurable"]` every turn. |

### Lifetime markers

Import the markers from `ze_sdk.types`. Annotate each `state_extensions()` field with one of them:

| Marker | Meaning |
|--------|---------|
| `Turn(reset=...)` or `Turn(factory=list)` | Reset at every turn and every workflow step. Pass an immutable `reset`, or a `factory` for a list or dict. |
| `Input()` | Supplied by whoever starts the turn. The reset leaves it alone. |
| `Thread("reason")` | Kept across turns. The reason is required. |
| `Run("reason")` | Kept across the steps of one workflow run. The reason is required. |

```python
from typing import Annotated, TypedDict

from ze_sdk.types import Run, Turn


class MyState(TypedDict, total=False):
    pending_note: Annotated[str | None, Turn()]
    step_notes: Annotated[list[str], Turn(factory=list)]
    review_count: Annotated[int, Run("counts reviews across the steps of one run")]
```

`ze_sdk.types` also exports `ConductorState`, `DelegateTally`, `ProcedureInvocation` and `WriteGateState`. These are the typed values that `AgentContext` carries as one field each.

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

`ze-api` calls this hook for every plugin while it registers proactive jobs (`ze_api/wiring/jobs.py`). `ProactiveScheduler.register(job, cron)` takes a job with a `job_id` and an async `run()` method.

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
| `ProactiveJob` | Protocol. Set `job_id: str` and implement `async run() -> None`. |
| `proactive_job` | Class decorator that checks the class defines a `job_id`. It does not register the job. |
| `ProactiveScheduler` | APScheduler wrapper. Call `register(job, cron)` inside `register_proactive_jobs`, or `add_cron_job(fn, cron, job_id)` for a bare coroutine function. |
| `ProactiveNotifier` | The one proactive send path. Call `notify(kind, title, body, ...)`; the interruption governor decides delivery. |
| `PushKind` | A declared kind of push: event type, class (`requested`/`accountability`/`discretionary`), urgency (`low`/`normal`/`high`), source. |
| `PushOutcome` | What the governor did with a push: `delivered`, `held`, `suppressed_budget`, `duplicate`, `deduped`, `failed`. |
| `PushLogStore` | Delivery audit log. Persists which notifications have been sent. |
| `PushLogEntry` | Dataclass for a single log entry. |
| `PushClass`, `Urgency` | The `Literal` types behind `PushKind.push_class` and `PushKind.urgency`. |
| `NotificationStore` | Store for the notification center rows. |

---

## `ze_sdk.channels` — channel abstraction

| Symbol | Description |
|--------|-------------|
| `Channel` | ABC for outbound message channels. Implement the `channel_type` property, `send` and `get_thread`. |
| `InboundChannel` | `Channel` that also receives messages. Implement `poll_new_messages(since)`; override `supports_push` and `webhook_verifier()` for push channels. |
| `ChannelRegistry` | Registry of channel instances by `ChannelType`. Inbound channels are also found by channel id. |
| `InboundMessage` | A message received on an `InboundChannel`. |
| `WebhookPayload`, `WebhookVerifier` | Inbound webhook request and the verifier a push channel returns. |
| `ChannelType` | Enum — `EMAIL`, `LINKEDIN`, `WHATSAPP`. |
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
| `MemoryContext` | Retrieval result: `facts`, `episodes`, `session_summaries`, `events`, `procedures`, `task_state`, `profile`, `entities`, `token_estimate`. |
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
| `ArtifactStatus` | Enum: `pending`, `promoted`, `rejected`. |
| `CompanionPolicy`, `ResearchPolicy`, `GoalsPolicy`, `WorkflowPolicy`, `PlannerPolicy`, `CalendarPolicy`, `RemindersPolicy`, `EmailPolicy`, `ProspectingPolicy` | Memory read policies. Return them from `ZePlugin.memory_policies()`. |
| `build_admission_gate` | Builds the signal admission gate from the `correlation.salience` config block. Pass the result to a job that submits signals. |
| `extract_facts`, `fact_extraction_model` | Run the fact extractor on text. Submit the result through `submit_perception_facts`. |
| `WORKS_ON`, `COLLABORATES_WITH` | Graph predicates for social-cognition edges. |
| `Relationship`, `GraphStore` | Graph edge type and the store protocol for reading and writing edges. |
| `submit_perception_facts`, `fact_to_contribution`, `PerceptionFactSubmit` | Submit extracted facts through the contribution seam. |
| `FactRestoreConflictError` | Error the memory store raises when a fact restore conflicts. |
| `ProcedureCandidate`, `ProcedureSourceKind`, `ProcedureAdmissionService`, `ProcedureActivator`, `ProcedureDiscovery`, `candidate_from_procedure`, `candidate_from_action_pattern`, `intersect_tools`, `format_procedure_guidance` | Governed procedure lifecycle: candidates, admission, discovery and activation. |

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
| `ActionRecorder`, `ActionRecordStore`, `safe_record_action`, `submit_action_record` | Record actions in the action ledger. |
| `ActionRecord`, `ActionRecordDraft`, `ActionContext`, `ActionLifecycle`, `ActionOutcome`, `AuthoritativeRef`, `CausalRef` | Types of an action record. |
| `FeedbackRecord`, `FeedbackRecordDraft`, `FeedbackKind`, `FeedbackStore`, `feedback_contribution`, `submit_feedback_record` | Reply feedback evidence. |
| `CollisionLogStore` | Store protocol for the collision log. |

---

## `ze_sdk.automation` — goals and workflows

Re-exports the goal and workflow types, stores and contracts: `Goal`, `Milestone`, `VerificationGate`, `GoalStore`, `GoalSuggestionStore`, `GoalLearning`, `StuckGoal`, `Workflow`, `WorkflowStep`, `WorkflowExecution`, `StepResult`, `WorkflowStore`, `WorkflowScheduler`, `AutomationPlanner` and `AutomationStore`.

## `ze_sdk.correlation` — hypotheses

`Hypothesis`, `HypothesisEvidence`, `HypothesisStore` (the protocol a plugin depends on), `PostgresHypothesisStore` and `HypothesisNotFoundError`.

## `ze_sdk.ui` — UI contributions

`UiContribution`, `UiManifest`, `ModuleSubject`, `ModuleResult`, `collect_ui_contributions`, `filter_ui_manifest_by_openapi`, `request_module_refresh` and `validate_plugin_tree`. See [Adding UI to a plugin](extending-ze.md#adding-ui-to-a-plugin).

---

## `ze_sdk.api` — REST helpers

| Symbol | Description |
|--------|-------------|
| `require_api_key` | FastAPI dependency that checks the bearer token. Use it on plugin REST routes. |

---

## `ze_sdk.errors` — error hierarchy

Always raise a typed `ZeCoreError` subclass. Never raise bare `Exception` or `ValueError`.

| Error class | When to raise |
|-------------|--------------|
| `ZeCoreError` | Base class (`ze_agents.errors` also names it `ZeError`). Do not raise directly. |
| `AgentError` | Unrecoverable agent-level failure (unexpected LLM response, missing result). |
| `AgentAbortedError` | Agent loop was cancelled via `AbortToken`. |
| `AgentConfigError` | Misconfiguration detected at startup (missing type hints, unregistered tool). |
| `ChannelSendError` | Channel `send()` failed. |
| `UndeclaredLifetimeError` | A graph-state field has no lifetime marker. Graph build fails at startup. |

The module also exports the rest of the hierarchy, such as `AgentTimeoutError`, `UnknownToolError`, `GoalError`, `WorkflowError`, `LLMJsonParseError` and `UiActionRefusedError`.

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
