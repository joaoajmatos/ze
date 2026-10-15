# Contract: WRITE tool declaration (ze-agents / ze-sdk `@tool`)

Plugin authors import `tool`, `ToolAccess`, `ToolReversibility`, `AskDecision` from `ze_sdk`.

```python
# Asks first by default: IRREVERSIBLE, no asks_first argument.
@tool(
    access=ToolAccess.WRITE,
    reversibility=ToolReversibility.IRREVERSIBLE,
    effect_phrase="deleted a calendar event",
    constraint_gate=True,
    summarize=lambda a: f"{a.get('summary', 'event')} — {a.get('start', '')}",
    description="…",
)
async def delete_event(...): ...

# Opt out: reason required.
@tool(
    access=ToolAccess.WRITE,
    reversibility=ToolReversibility.IRREVERSIBLE,
    asks_first=False,
    no_ask_reason="Saves content the user asked to save; nothing leaves Ze.",
    effect_phrase="ingested text",
    description="…",
)
async def ingest_text(...): ...

# Editable item.
@tool(..., reversibility=ToolReversibility.IRREVERSIBLE, editable_field="body", ...)
async def send_email(to: str, subject: str, body: str, ...): ...

# Pre-call check (workspace, plan approval).
def workspace_ask_check(args: dict, ctx) -> AskDecision: ...
@tool(..., asks_first=False, no_ask_reason="WorkspaceGate decides per action and origin",
      ask_check=workspace_ask_check, ...)
async def workspace_run(...): ...
```

Registration rules (fail with `AgentConfigError` at import):

| Declaration | Allowed when |
|---|---|
| `asks_first=False` | WRITE + IRREVERSIBLE, with non-empty `no_ask_reason` |
| `no_ask_reason` | only with `asks_first=False` |
| `asks_first=True` | never written explicitly (it is the IRREVERSIBLE default); rejected to keep one spelling |
| `ask_check` | WRITE tools |
| `editable_field` | WRITE tools; must name a parameter of the function |
| `summarize` | any WRITE tool |

Behaviour guarantees for tool authors:
- An asks-first tool's function body runs only after the user approved that exact call (or a plan pre-approved it). A tool body never raises a confirmation itself; `ToolConfirmationRequired` no longer exists.
- `ask_check` must be cheap and side-effect free; it runs on every call and again never after approval.
- Asks-first tools must be called through `agentic_loop` (or `delegate_to_agent`). `call_tool` on an asks-first tool outside a loop (no `ctx.loop_active`) raises `AgentConfigError("asks-first tool called outside the agent loop")`.
