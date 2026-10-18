# Data Model: Programmatic Tool Use (197)

No migration.

## ze-agents (in process)

**ScriptLimits** (frozen): `wall_seconds=30`, `max_inner_calls=20`, `max_spend_usd=0.05`, `max_result_chars=4000`, `max_source_chars=8000`. `from_config(config)` reads `workspace.scripts`; a missing or invalid field (wrong type, non-positive) falls back with a warning.

**ScriptRequest**: `seq: int`, `tool: str`, `args: dict[str, Any]`.

**DispatchReply**: `ok: bool`, `value: Any = None`, `error: str | None = None`, `stop: bool = False`.

**ScriptOutcome**: `status: "ok" | "exception" | "timeout" | "killed" | "bad_request" | "busy" | "unavailable"`, `value: Any`, `writes: list[{"tool": str, "args": dict}]`, `stderr_tail: str`, `exception: str | None`.

**ScriptRunner** (Protocol): `run(*, script_id, source, stub, limits, dispatch) -> ScriptOutcome`.

**ScriptBudget**: `limit_usd: float`, `spent_usd: float`; `current_script_budget` ContextVar; `charge_script(usd)`.

**ToolCall** additions: `parent_call_id: str | None = None`, `inner_calls: list[ToolCall] = []`, `script: dict | None = None` (`source`, `source_cut`, `outcome`, `limit`, `source_hash`, `procedure_id`). Checkpointed with `ParkedLoop.accumulated` like other fields.

**AgentContext** addition: `script_runner: ScriptRunner | None` (runtime only, never checkpointed, `repr=False`).

**BaseAgent** addition: `script_tools: bool = False` (class attribute).

## Trace (`messages.trace` JSON)

**ToolCallTrace** additions: `parent_call_id: str | None`, `script: ScriptTrace | None`.

**ScriptTrace**: `source: str` (≤ 8,000 chars), `source_cut: bool`, `outcome: str`, `limit: str | None` (`wall_time`, `inner_calls`, `spend`, `result_size`), `source_hash: str`, `procedure_id: str | None`.

Same fields on `ToolCallTraceResponse` and the `trace_update` tool rows.

## Ledger and procedures (existing tables)

**action_records** row per finished script: `producer_kind = "workspace"`, `source_record_type = "tool_script"`, `source_record_id = <sha256 hex>`, `action_kind = "run"`, `outcome = succeeded | failed`, `actor` = the calling agent, `summary = "Script by <agent>: <n> tool calls"`, context `message_id`/`thread_id` when known.

**ProcedureSourceKind** addition: `TOOL_SCRIPT = "tool_script"`.

**ProcedureMatch** addition: `source_kind: str | None = None`.

**Script procedure candidate**: `source_kind = tool_script`, `name = "script:<hash[:12]>"`, `trigger` = first 120 chars of the user turn, `steps = [normalized source]`, `success_criteria = ["script ends ok"]`, `limits` = sorted inner tool names, `evidence_refs` = the three action record ids.

## Config

```yaml
workspace:
  scripts:
    wall_seconds: 30
    max_inner_calls: 20
    max_spend_usd: 0.05
    max_result_chars: 4000
    max_source_chars: 8000
```
