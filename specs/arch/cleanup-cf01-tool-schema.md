# CF-01 — Tool schema contract (R-07)

Status: Implemented on floor CF-01 (2026-10-16). Finding R-07 in
`specs/arch/cleanup-report-2026-10.md` §7.

## Problem

`ToolSpec.llm_schema()` kept a parameter only when its annotation was exactly
`str`, `int`, `float`, `bool`, `list` or `dict`. Two failures followed:

1. Parameters meant for the model vanished when typed `X | None` or `list[X]`.
2. Injected parameters typed as plain scalars showed in the schema, and
   `_merge_deps` let a model value override the injected one.

Runtime dump of every registered tool on `0f7f0432`:

| Kind | Tool and parameters |
|---|---|
| Hidden, meant for the model | `update_event.summary/start/end/description`; `send_email.thread_id`; `world_time.locations` (required, so the tool could not be called correctly); `get_positions.account_id`; `get_spending_summary` / `get_transactions.account_id/since/until`; `get_recurring_expenses.status`; `search_news.tags`; `get_headlines.tags`; `add_prospect.company/role` (required Python args the model could not send, so every call failed) |
| Visible, but injected | `browser_extract.browser_delay_ms/browser_max_text_chars` (required); `draft_outreach.model` (required); `add_prospect` / `draft_outreach.campaign_id` (required; a model value replaced the real campaign id); `get_headlines._diagnostic_query/_min_preferences` |
| Would leak under a naive fix | `create_workflow` / `edit_workflow_steps.session_id/user_message_id`; `restore_priority_override.prior_override_id`; `forget_fact.restore_fact_ids` |

## Contract

1. **Marker.** `Injected` in `ze_agents.tool`, re-exported from `ze_sdk`, is a
   generic alias for `Annotated[T, <marker>]`:
   `session_id: Injected[str | None] = None`. Type checkers see `T`.
2. **Visibility.** A parameter is model-visible unless it is `Injected[...]` or a
   dependency type. A dependency type is a class or Protocol that is not a JSON
   type, `Any`, `object`, a callable, an unannotated parameter, or an annotation
   that does not resolve at runtime (`TYPE_CHECKING` imports).
3. **JSON types.** `str` → string, `int` → integer, `float` → number, `bool` →
   boolean, `dict` / `dict[str, X]` → object, `list` → array, `list[X]` → array
   with typed `items`. `X | None` emits the schema of `X`. A union whose members
   are all dependencies is a dependency. A parameter is required when it has no
   default.
4. **Registration fails** (`AgentConfigError`) for a visible parameter whose type
   is data-shaped but has no JSON form: `set`, `frozenset`, `tuple`, `bytes`,
   `Literal`, `Enum`, `date` / `datetime` / `time` / `timedelta`, `UUID`,
   `Decimal`, `Path`, any `collections.abc` iterable (`Sequence`, `Mapping`,
   `Set`, `Iterable`, bare or parametrized), a union of several JSON types, a
   union of a dependency (or `Injected`) type with a JSON type, `list` of a
   dependency, `dict` with non-`str` keys. The message says to use `str` or mark
   the parameter `Injected`.
   Known limit: an annotation that does not resolve at runtime (a
   `TYPE_CHECKING`-only import) is treated as a dependency and hidden, because
   its type cannot be inspected. Data types such as `datetime` are always
   importable, so the list above still catches them.
5. **Model values for hidden parameters are dropped** in the agentic loop before
   deps merge (`_model_args`). The stored `ToolCall.args` is the filtered dict.
   `ToolSpec.hidden_params()` names the hidden set. The schema and hidden set
   are computed once at registration and cached on the `ToolSpec`.
6. **Undo path unchanged.** `BaseAgent.run_undo` still passes undo-payload args
   (`restore_*`) through to `Injected` parameters.
7. `_schema_override` (render tools) is unchanged and filters nothing.

## Checks

- `core/contracts/ze-agents/tests/test_tool.py`: optional, list, dict, injected,
  dependency, `hidden_params`, registration failure per unsupported shape.
- `core/contracts/ze-agents/tests/test_base_agent_loop.py`: the model cannot set
  an `Injected` or dependency parameter.
- `core/contracts/ze-agents/tests/test_run_undo.py`: undo payload reaches an
  `Injected` parameter.
- `apps/ze-api/tests/test_tool_schemas.py`: every affected plugin tool, visible
  and hidden sides, and no tool exposes `session_id`, `user_message_id` or `ctx`.
- Eval scenarios (tag `tool_schema`): `calendar_update_event_time`,
  `calendar_world_time_locations`, `email_reply_in_thread`,
  `prospecting_add_prospect_company_role`, `routing_finance_spending_since`,
  `routing_news_tags`.

`nli_grounding` (also hidden) was deleted under U-02; no check.
