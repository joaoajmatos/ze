# Data Model: Programmatic Tool Use (197)

No migration.

## ze-agents (in process)

**ScriptLimits** (frozen): config fields `wall_seconds=30`, `max_inner_calls=20`, `max_proposed_writes=10`, `max_spend_usd=0.05`, `max_result_chars=4000`, `max_source_chars=8000`; code constants `max_request_bytes=262144`, `max_reply_bytes=1048576`, `inner_result_store_chars=2000`. `from_config(config)` reads `workspace.scripts`; a missing or invalid field (wrong type, non-positive) falls back with a warning.

**Sandbox limits** (sidecar constants): `RLIMIT_AS` 256 MiB, `RLIMIT_NPROC` 32, `RLIMIT_FSIZE` 16 MiB, `RLIMIT_CPU` wall + 1 s, `RLIMIT_NOFILE` 64, scratch 32 MiB, stderr ring 64 KB, WS `max_size` 2 MiB.

**ScriptRequest**: `seq: int`, `tool: str`, `args: dict[str, Any]`.

**DispatchReply**: `ok: bool`, `value: Any = None`, `error: str | None = None`, `stop: bool = False`.

**ScriptOutcome**: `status: "ok" | "exception" | "timeout" | "killed" | "bad_request" | "busy" | "unavailable" | "resource_limit"`, `value: Any`, `writes: list[{"tool": str, "args": dict}]`, `stderr_tail: str`, `exception: str | None`.

**ScriptRunner** (Protocol): `run(*, script_id, agent, source, stub, limits, dispatch, procedure_id=None, context=None) -> ScriptOutcome`. `procedure_id` marks a rerun, which never submits a candidate; `context` is `ScriptContext(user_turn, message_id, thread_id)` for the ledger and the candidate trigger.

**ScriptBudget**: `limit_usd: float`, `spent_usd: float`; `current_script_budget` ContextVar; `charge_script(usd)`. **`in_script_call`**: ContextVar[bool], set around each inner call; `ToolCallCapHook` skips counting while it is set.

**ToolSpec** additions: `produces_ui: bool = False` (`@tool(produces_ui=True)`; every `render_*` tool and the `show_*` compose tools); `egress: bool = False` (`@tool(egress=True)`; READ tools that reach a caller-chosen URL or host, `browser_extract` today). Both are excluded from the script stub.

**ToolCall** additions: `parent_call_id: str | None = None`, `inner_calls: list[ToolCall] = []`, `script: dict | None = None` (`source`, `source_cut`, `outcome`, `limit`, `source_hash`, `procedure_id`). Checkpointed with `ParkedLoop.accumulated` like other fields.

**AgentContext** addition: `script_runner: ScriptRunner | None` (runtime only, never checkpointed, `repr=False`).

## Trace (`messages.trace` JSON)

**ToolCallTrace** additions: `parent_call_id: str | None`, `script: ScriptTrace | None`; `access` gains the value `"script"` (treated as read by Retry).

**ScriptTrace**: `source: str` (≤ 8,000 chars), `source_cut: bool`, `outcome: str`, `limit: str | None` (`wall_time`, `inner_calls`, `spend`, `result_size`), `source_hash: str`, `procedure_id: str | None`.

Same fields on `ToolCallTraceResponse` and the `trace_update` tool rows.

## Ledger and procedures (existing tables)

**action_records** row per run: `producer_kind = "workspace"`, `source_record_type = "tool_script"`, `source_record_id = <script id uuid>` (unique idempotency key per run), `action_kind = "run"`, lifecycle `SUCCEEDED | FAILED | TIMED_OUT` with outcome `SUCCESS | FAILURE | TIMEOUT` and `failure_code` from the outcome status, `actor` = the calling agent, `summary = "Script by <agent>: <n> tool calls"`, context `script_key` (tool signature) plus `message_id`/`thread_id` when known.

**ActionContext** addition: `script_key: str | None = None` (in the existing `context` JSONB). **ActionRecordStore** addition: `list_by_script_key(script_key, limit=3)`.

**ProcedureSourceKind** addition: `TOOL_SCRIPT = "tool_script"`.

**ProcedureMatch** addition: `source_kind: str | None = None`.

**Script procedure candidate**: `source_kind = tool_script`, `name = "Script: <tool1 → tool2 …> [<script_key[:8]>]"` (≤ 120 chars), `trigger` = first 120 chars of the user turn, `preconditions = []`, `steps = [latest successful source]`, `success_criteria = ["script ends ok"]`, `limits` = ordered inner tool names, `evidence_refs` = the three action record ids. `validate_candidate` requires evidence and one step of at most 8,000 chars for this kind.

## Config

```yaml
workspace:
  scripts:
    wall_seconds: 30
    max_inner_calls: 20
    max_proposed_writes: 10
    max_spend_usd: 0.05
    max_result_chars: 4000
    max_source_chars: 8000
```
