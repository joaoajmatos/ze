# Extending Ze

Ze is extended through **plugins** — self-contained domain packages that contribute
agents, proactive jobs, channels, and graph behavior without touching the engine.
This guide covers the full lifecycle of building an extension: from deciding where code
belongs to wiring it into the running app.

Read this alongside:
- [docs/sdk.md](sdk.md) — SDK symbol reference
- [docs/adding-an-agent.md](adding-an-agent.md) — agent authoring details
- [docs/package-architecture.md](package-architecture.md) — package layout and dependency rules
- [docs/skills.md](skills.md) — bundled `SKILL.md` files via `bundled_skill_paths()`

---

## Where does my code belong?

Start here before writing anything.

![Flowchart showing where new code belongs: an agent for an existing domain routes to ze-personal, ze-automation, ze-messenger, ze-calendar, or ze-prospecting; an agent for a new domain gets its own plugin package; a proactive job lives in the agent's own package via the ZePlugin hook; and infrastructure additions route to ze-memory, ze-data, ze-agents/ze-onboarding, ze-workspace/ze-browser, ze-notifications, or ze-components.](diagrams/docs/package-routing.svg)

<sub>[Interactive version](diagrams/docs/package-routing.html)</sub>

New agent that needs contacts or persona context routes to `ze-personal` (`ze_personal/agents/<name>/`). Goals or workflows go to `ze-automation` (`ze_automation/agents/<name>/`). Email/Gmail agents go to `ze-messenger` (`ze_messenger/agents/messenger/`). Calendar/reminders go to `ze-calendar` (`ze_calendar/agents/<name>/`). Prospecting/outreach goes to `ze-prospecting` (`ze_prospecting/agents/`). A new coherent domain (finance, health) gets a new plugin package — see "Creating a new plugin package" below.

See [docs/package-architecture.md](package-architecture.md) for the full decision table and the criteria for when a new package is warranted.

---

## Adding an agent to an existing plugin

The short path — no new package needed.

### 1. Write a spec first

Every implementation starts with a spec in `specs/phases/`. Create it with `/speckit-specify` (see `specs/README.md`).
Resolve all open questions before writing code.

### 2. Create the agent files

```
plugins/<pkg>/<module>/agents/<name>/
    __init__.py
    agent.py      ← @agent class + _AGENT_INSTRUCTIONS
    tools.py      ← @tool functions (omit if no Python tools needed)
```

### 3. Define tools (`tools.py`)

```python
from ze_sdk import tool, ToolAccess, ToolReversibility

@tool(access=ToolAccess.READ, description="Fetch records from the store.")
async def get_record(id: str, store: MyStore) -> str:
    result = await store.get(id)
    return str(result)

@tool(
    access=ToolAccess.WRITE,
    description="Create a new record.",
    reversibility=ToolReversibility.REVERSIBLE,
    undo_tool="delete_record",
    undo_note="Does not restore links other records made to it",
    effect_phrase="created a record",
)
async def create_record(name: str, store: MyStore) -> str:
    record = await store.create(name)
    return f"Created: {record.id}"

@tool(
    access=ToolAccess.WRITE,
    description="Delete a record.",
    reversibility=ToolReversibility.IRREVERSIBLE,
    effect_phrase="deleted a record",
)
async def delete_record(id: str, store: MyStore) -> str:
    await store.delete(id)
    return f"Deleted: {id}"
```

Use `ToolAccess.READ` when there are no external side effects. Use `ToolAccess.WRITE`
for anything that creates, modifies, deletes, or sends. When in doubt, use `WRITE`.

Every `WRITE` tool must also declare `reversibility`. Use `REVERSIBLE` only when another
registered `WRITE` tool undoes the action. A `REVERSIBLE` tool names that tool in
`undo_tool` and says what the undo cannot restore in `undo_note`. Use `IRREVERSIBLE`
otherwise, and when in doubt. `effect_phrase` is a short past-tense description such as
`"created a record"`. Ze uses it to tell the user why Retry is unavailable. A `WRITE`
tool without `reversibility` fails at import with `AgentConfigError`. A `READ` tool must
declare none of these arguments. At startup Ze checks that each `undo_tool` names a
registered `WRITE` tool.

An `IRREVERSIBLE` `WRITE` tool asks the user first. It does not run until the user
approves that exact call. Pass `asks_first=False` with a non-empty `no_ask_reason` only
when the tool needs no confirmation. Registration fails without the reason. Use
`editable_field` to let the user edit one parameter in the confirmation, and `summarize`
to write the one-line summary the user sees. See [docs/sdk.md](sdk.md#asks-first).

### 4. Write the agent (`agent.py`)

```python
from ze_sdk import agent, BaseAgent
from ze_sdk.types import AgentContext, AgentResult

_AGENT_INSTRUCTIONS = """
You are Ze's <name> agent. <Purpose, scope, tone.>

Guidelines:
- <specific constraint>
""".strip()


@agent
class MyAgent(BaseAgent):
    name         = "my_agent"
    description  = "One or two sentences. Embedded for routing — be specific."
    model        = "anthropic/claude-sonnet-4-5"
    timeout      = 30
    tools        = ["get_record", "create_record"]

    def __init__(self, store: MyStore) -> None:
        self._store = store

    async def run(self, ctx: AgentContext) -> AgentResult:
        system = self._build_system_prompt(_AGENT_INSTRUCTIONS, ctx)
        messages = [{"role": "user", "content": ctx.prompt}]

        response, tool_calls = await self.agentic_loop(
            ctx, self._client, messages, system,
            deps={"store": self._store},
        )

        return AgentResult(agent=self.name, response=response, tool_calls=tool_calls)
```

**All `__init__` parameters must be type-annotated.** The bootstrapper uses
`get_type_hints()` — unannotated parameters raise `AgentConfigError` at startup.

### 5. Register with the plugin

```python
# In plugins/<pkg>/<module>/plugin.py
def agent_module_paths(self) -> list[str]:
    return [
        "mypkg.agents.myagent.tools",   # tools first — @tool registers on import
        "mypkg.agents.myagent.agent",
    ]
```

### 6. Add shared deps only when needed

Plugin discovery is automatic via the `ze.plugins` entry point. If your agent's
`__init__` takes a type that is not already in the bootstrap dep map, either:

- contribute it from an existing plugin via `agent_deps()`, or
- add the service to `plugin_deps` in `ze_api/container.py` inside `build_container()`
  when it is a shared infra type constructed before plugins load.

`NLIClient`, `LLMClient`, `SentenceTransformer` (embedder), and `asyncpg.Pool` are
already in the dep map — annotate them on your `ZePlugin.__init__` when a job or
service needs them (see Phase 81 news credibility/dedup and finance merchant merge).

### 7. Register memory and checkpoint hooks

```python
def memory_policies(self) -> dict:
    from ze_memory.policies import MyAgentPolicy
    return {"my_agent": MyAgentPolicy()}

def checkpoint_serde_modules(self) -> tuple[str, ...]:
    return ("ze_myplugin.types",)
```

### 8. Write tests

```
plugins/<pkg>/tests/agents/<name>/
    __init__.py
    test_agent.py
    test_tools.py
```

- No real API calls — mock `client.complete_with_tools` with `AsyncMock`.
- No real DB — mock `pool.acquire()` with `AsyncMock`.
- Build `AgentContext` directly (it's a dataclass).
- Test the park path: call each asks-first tool through `agentic_loop`, assert that it
  parks with its exact arguments, and assert that the function body did not run.

---

## Creating a new plugin package

Use this path when you have a coherent new domain (e.g. finance, health) that warrants
its own package. Read [docs/package-architecture.md](package-architecture.md#when-to-create-a-new-package)
first to confirm a new package is justified.

### 1. Scaffold the package

```
plugins/ze-myplugin/
    pyproject.toml
    ze_myplugin/
        __init__.py
        plugin.py
        types.py          ← domain dataclasses (never Pydantic)
        locales/
            en.yaml       ← progress message keys for this plugin
            pt.yaml
        agents/
            myagent/
                __init__.py
                agent.py
                tools.py
        jobs/
            myjob.py
        store.py
    tests/
        __init__.py
        agents/
            myagent/
                test_agent.py
```

### 2. `pyproject.toml`

```toml
[project]
name = "ze-myplugin"
version = "0.1.0"
dependencies = ["ze-sdk"]     # only Ze dep a plugin needs

[project.entry-points."ze.plugins"]
ze_myplugin = "ze_myplugin.plugin:MyPlugin"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

The `ze.plugins` entry point is the contract that declares the plugin's existence to Ze.

### 3. Implement the plugin

```python
# ze_myplugin/plugin.py
from pathlib import Path
from ze_sdk import ZePlugin

class MyPlugin(ZePlugin):

    def __init__(self, store: MyStore) -> None:
        self._store = store

    def agent_module_paths(self) -> list[str]:
        return [
            "ze_myplugin.agents.myagent.tools",
            "ze_myplugin.agents.myagent.agent",
        ]

    def bundled_skill_paths(self) -> list[str]:
        return [str(Path(__file__).parent / "skills" / "my-skill" / "SKILL.md")]

    @classmethod
    def migrations_path(cls) -> Path | None:
        return Path(__file__).parent / "migrations"

    def configurable_services(self) -> dict:
        return {"my_store": self._store}

    def memory_policies(self) -> dict:
        from ze_memory.policies import MyAgentPolicy
        return {"my_agent": MyAgentPolicy()}

    def checkpoint_serde_modules(self) -> tuple[str, ...]:
        return ("ze_myplugin.types",)

    async def startup(self, container) -> None:
        await self._store.connect()

    async def shutdown(self) -> None:
        await self._store.close()

    def register_proactive_jobs(self, scheduler, settings, *, consolidation_enabled=True) -> None:
        from ze_myplugin.jobs.myjob import MyJob
        scheduler.register(MyJob(self._store, settings), cron="0 9 * * *")
```

Override only what you need — all methods have no-op defaults.

### 3b. Add progress message translations

Create `ze_myplugin/locales/en.yaml` (and `pt.yaml` for Portuguese):

```yaml
# ze_myplugin/locales/en.yaml
my_agent:
  working:
    - "⚙️ Working on that..."
    - "⚙️ Let me handle that..."
```

The `ZePlugin` base class auto-loads these files via `locale_data()` at startup and
merges them into the shared `ProgressTranslations`. No override needed — just follow
the `locales/{locale}.yaml` convention. Agents call `await self.emit(ctx, "my_agent.working")`
to send the message to the client.

The app-level `config/locales/` files are an override layer — add entries there only
to customize a plugin's messages for a specific deployment without touching plugin code.

### 4. Add to `ze-api` dependencies

```toml
# apps/ze-api/pyproject.toml
[project]
dependencies = [
    ...
    "ze-myplugin",
]
```

Ze discovers and instantiates the plugin at startup via the entry point. Only add
types to `plugin_deps` in `build_container()` when the plugin constructor needs a
shared service that is not already in the dep map.

### 5. Create a database migration

Create a `migrations/` directory (with `env.py` and `versions/`) in your package and override `migrations_path()` on your
`ZePlugin` subclass to return it. Use a package-specific revision prefix (`zcal`, `zn`, `zfin`, …)
and filename pattern `{revision}_{feature}.py`. Write raw SQL via `op.execute()` — no ORM.

See `AGENTS.md` § Migration ownership and `plugins/ze-calendar/ze_calendar/migrations/` for an example.

---

## Adding a proactive job

Background jobs run on a cron schedule and push notifications to the user.

### 1. Implement the job

```python
# ze_myplugin/jobs/myjob.py
from ze_sdk.proactive import proactive_job, ProactiveNotifier, PushKind
from ze_agents.settings import Settings

# Declare the kind once, at module level. The first argument is the event type.
MY_PLUGIN_INSIGHT = PushKind(
    "my_plugin_insight", "discretionary", "normal", "my_plugin"
)

@proactive_job
class MyJob:
    job_id   = "my_plugin.my_job"
    schedule = "0 9 * * 1"   # every Monday 09:00

    def __init__(self, store: MyStore, settings: Settings, notifier: ProactiveNotifier) -> None:
        self._store = store
        self._settings = settings
        self._notifier = notifier

    async def run(self) -> None:
        data = await self._store.fetch_summary()
        if not data:
            return
        await self._notifier.notify(
            MY_PLUGIN_INSIGHT,
            title="Weekly summary",
            body=data,
            budget_key=f"insight:{data.id}",
        )
```

Pick the class by who asked for the push: `requested` for a reminder the user set, `accountability` for a report the user switched on, and `discretionary` for a nudge Ze chose to send. Only a `discretionary` push needs a `budget_key`.

### 2. Register in the plugin

```python
def register_proactive_jobs(self, scheduler, settings, *, consolidation_enabled=True) -> None:
    from ze_myplugin.jobs.myjob import MyJob
    scheduler.register(
        MyJob(self._store, settings, self._notifier), cron="0 9 * * 1"
    )
```

---

## Adding a channel

Channels represent message transports (email, SMS, etc.). `Channel` has one abstract property (`channel_type`) and two abstract methods (`send`, `get_thread`); `InboundChannel` adds polling for new messages. See [channels.md](channels.md) for the full contract, thread routing, and the inbound pipeline.

```python
from ze_sdk.channels import Channel, ChannelType, Message, SentMessage, Thread

class MyChannel(Channel):
    @property
    def channel_type(self) -> ChannelType: ...

    async def send(self, message: Message) -> SentMessage: ...
    async def get_thread(self, thread_id: str) -> Thread: ...
```

Return instances from `ZePlugin.channels()`. `ze-api` collects them into the shared `ChannelRegistry`.

---

## Let the user point at your records

If your plugin owns a record the user can look at, such as a reminder or an article, register a screen resolver so "this" and "Chat about this" work on it. Return resolvers from `ZePlugin.screen_resolvers()`; see [Screen resolvers](sdk.md#screen-resolvers) for the contract. On the web side, publish the page's subject with `useScreenPublisher` and pass `onChatAbout` to the `Module` that frames the record. If something emits refs of a new kind, add its kind to the resolver and test that a missing record gives a `missing` line.

## Write confirmation

Ze asks before an irreversible write runs. The rule comes from the tool declaration,
not from the agent or the route. A `WRITE` tool that is `IRREVERSIBLE` parks until the
user approves it. A `REVERSIBLE` tool runs without asking. Use the declaration to
choose the behavior:

| Declaration | Effect |
|---|---|
| `IRREVERSIBLE` (default) | The call parks. The user approves or denies that exact call. |
| `asks_first=False` + `no_ask_reason` | The call runs without asking. The reason is required. |
| `REVERSIBLE` + `undo_tool` | The call runs without asking. Ze records the undo. |

Choose `IRREVERSIBLE` for any action with real-world consequences, such as sending an
email, creating or deleting a calendar event, or spending money.

---

## Let a screen run your tool

A button in a tree you build can run one of your agent's write tools. Opt the tool in and give it a line to show on success:

```python
@tool(access=ToolAccess.WRITE, ui_action=True, done_phrase="Marked as read.")
async def mark_source_read(source_id: str, ...): ...
```

Then build the button with `ToolAction(owner="news", tool="mark_source_read", args={"source_id": "s-12"})`. Args are scalars. The press goes through the same write gates as chat, including the confirmation for an irreversible tool. A READ tool cannot opt in. See [native-interface.md](native-interface.md#screen-tool-actions).

## Error handling

Raise typed errors from `ze_sdk.errors`. Never raise bare `Exception` or `ValueError`.

```python
from ze_sdk.errors import AgentError

# In a tool:
if not result:
    raise AgentError("Record not found — cannot proceed.")

```

The error hierarchy:
- `ZeError` — base class
  - `AgentError` — unrecoverable agent failure
    - `AgentAbortedError` — loop cancelled via `AbortToken`
    - `AgentConfigError` — misconfiguration caught at startup
  - `ChannelError` — channel failure
    - `ChannelSendError` — channel transport failure

`ze_sdk.errors` re-exports these and the rest of the hierarchy (workflow, goal, persona, contribution errors, and more).

---

## Checklist

### New agent in an existing plugin

- [ ] Spec written in `specs/phases/`
- [ ] `agent.py` with `@agent` class — `name`, `description`, `model`, `tools` set
- [ ] `tools.py` with `@tool` functions — `access` and `description` set on each; `reversibility` and `effect_phrase` set on each `WRITE` tool
- [ ] Module paths added to `plugin.agent_module_paths()` (tools module listed first)
- [ ] All `__init__` parameters type-annotated
- [ ] New shared dependencies added to `plugin_deps` in `ze_api/container.py` (only when no plugin already provides the type)
- [ ] Progress keys added to `locales/en.yaml` (and `pt.yaml`) in the plugin package
- [ ] Tests cover the golden path and the park path for asks-first tools

### New plugin package

- [ ] Spec written in `specs/phases/` or `specs/arch/`
- [ ] `pyproject.toml` with `ze-sdk` as the only Ze dep and `ze.plugins` entry point
- [ ] `plugin.py` implementing `ZePlugin` — only overrides methods it needs
- [ ] `locales/en.yaml` (and `pt.yaml`) with progress keys for all agents in the plugin
- [ ] `ZePlugin.onboarding()` implemented if the plugin needs first-run setup questions
- [ ] Package added to `ze-api/pyproject.toml` dependencies
- [ ] Alembic migrations in `migrations/versions/` if the plugin owns tables, with `migrations_path()` overridden
- [ ] `tests/` directory with its own `pyproject.toml` or in-tree conftest
- [ ] `startup()` and `shutdown()` implemented if the plugin holds long-lived resources
