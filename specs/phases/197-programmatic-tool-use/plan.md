# Implementation Plan: Programmatic Tool Use

**Branch**: `197-programmatic-tool-use` | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/197-programmatic-tool-use/spec.md` (clarified 2026-10-18).

## Summary

Every agent with at least one data read tool sees one harness tool, `run_tool_script`, handled in the agentic loop like `delegate_to_agent` (not a registry tool). The loop builds the agent's visible read-tool set, generates a Python stub from those tools' schemas, and hands source, stub and limits to a `ScriptRunner` (a Protocol in ze-agents, implemented in ze-workspace, wired by ze-api into the turn config). The runner opens a WebSocket to the sidecar; the sidecar runs the script as a no-network sandbox user in a throwaway directory and relays each framed request from a dedicated pipe. For each request the loop's dispatcher checks the name against the visible read set, the limits and the spend budget, then calls `call_tool` as the agent, so every gate, hook, cap and undo rule applies unchanged. The script's return value (capped) goes to the model; proposed writes run after the script as ordinary tool calls in the same loop iteration, so parking and confirmation reuse the 181 path. Each script step is a `ToolCall` holding its inner calls; the trace flattens them with `parent_call_id`. Every finished script is its own action record carrying its tool signature (agent + ordered tools called); three successes in a row for a signature submit one procedure candidate (`tool_script` source kind), and `run_tool_script(procedure_id=...)` reruns a validated script procedure with the stub built from the agent's tools at that moment.

**Build order**: after 187b lands (`ToolCall.call_id`, `started_at`, the per-call timing and the turn recorder used for spend attribution). Independent of 196.

## Technical Context

**Language/Version**: Python 3.12 (backend and sidecar), TypeScript 5 / React 19 (web)

**Primary Dependencies**: FastAPI WebSocket on the sidecar (uvicorn[standard] already installed), `websockets==16.0` (already pinned in ze-api) added to ze-workspace for the client, nftables in the sidecar image (already installed)

**Storage**: none new. Script steps live on `messages.trace` JSON; script runs are `action_records` rows (`source_record_type = "tool_script"`, existing table); procedure candidates use the existing `procedure_*` tables (`source_kind` is unconstrained TEXT, so `tool_script` needs no migration; verified in `zm022`). No migration.

**Testing**: pytest with a fake `ScriptRunner` for loop and gate tests; sidecar relay tests in the existing `sidecar/workspace/tests/` (run with the existing `make test-workspace-sidecar`; uid switching, rlimits and nft checks marked `docker`, run by the quickstart smoke test); vitest for the trace row; `eval/scenarios/tool_scripts.yaml` with a `max_llm_calls` assertion (live only with the user's OK).

**Target Platform**: ze-api and the workspace sidecar on Fly; ze-web SPA.

**Performance Goals**: script start (WS open to first request served) under 1 s on the sidecar; an inner read adds no model call.

**Constraints**: the sandbox never reaches Ze; no inner call bypasses `call_tool`; telemetry and learning never fail a turn; limits from config (`workspace.scripts`).

**Scale/Scope**: one script at a time per sidecar; up to 20 inner calls and 10 proposed writes per script; every agent with a data read tool.

## Constitution Check

| Principle | Status |
|---|---|
| I Spec first | Spec clarified 2026-10-18; ADR `specs/arch/programmatic-tool-use.md` in this phase |
| II Single user | One script slot; no tenancy |
| III Layered packages | Contract and dispatch in ze-agents (imports nothing from ze-workspace); runner in ze-workspace (already depends on ze-agents, ze-memory); wiring in ze-api; plugins change nothing (the capability is in `BaseAgent`) |
| IV Typed Python | `ScriptLimits`, `ScriptRequest`, `ScriptOutcome`, `ScriptTrace` dataclasses; typed `ScriptError(ZeError)` |
| V Tests first | Every task fail-first |
| VI Observable | Script steps, inner calls, limits and outcomes on the trace, REST, WS and web; one action record per run |
| VIII Pre-v1 hard cuts | No compatibility path; `ToolCall` and `ToolCallTrace` gain fields |

No violations.

## Blast radius (graphify affected + grep, 2026-10-18)

| Symbol | Callers / readers | Change |
|---|---|---|
| `BaseAgent.agentic_loop` (`base_agent.py:707`) | every agent `run()` | visible tool list may add `run_tool_script`; reply handling gains a script branch; proposed writes appended to the iteration's call list |
| `BaseAgent._visible_tool_names` (`base_agent.py:298`) | the loop | unchanged; the script dispatcher reuses it |
| `BaseAgent.call_tool` (`base_agent.py:355`) | loop, `run_undo`, resume | unchanged signature; called by the dispatcher with `_call_id` |
| `ToolCall` (`ze_agents/types.py:74`) | loop, delegate, trace, retry, rollback, checkpoints (`ParkedLoop.accumulated`) | gains `parent_call_id`, `inner_calls`, `script` |
| `flatten_tool_calls` (`ze_agents/nested_tools.py:29`) | `trace.py` `_extract_tool_calls`, retry eligibility, `track_loop_succeeded` | also flattens `inner_calls`, setting `parent_call_id` |
| `ToolCallTrace` (`conversation/messages/types.py:103`) | `record_trace`, REST, `trace_update`, retry plan | gains `parent_call_id`, `script` |
| `AgentContext` (`ze_agents/types.py`) | every agent | gains runtime-only `script_runner` (never checkpointed, like `procedure_matches`) |
| `execute_tool` (`orchestration/nodes/execution.py:290`) | graph | copies `config["configurable"]["script_runner"]` into the agent contexts it builds |
| `run_delegate` (`ze_agents/delegate.py:267`) | conductor | copies `script_runner` into `sub_ctx` |
| `ZeContainer._build_config` (`ze_api/wiring/container.py:312`) | every turn | adds `script_runner` |
| `build_workspace_stack`, `WorkspaceStack` (`ze_workspace/bootstrap.py:36-51`) | container | builds the runner; gains `procedure_admission` parameter and `script_runner` field |
| `ToolCallCapHook.on_tool_start` (`ze_agents/tool_cap_hook.py`) | every tool call | skips counting while `in_script_call` is set |
| `retry_eligibility` (`conversation/retry.py:101`) | Retry | treats `access == "script"` as read (an unregistered harness tool would otherwise read as `unknown` and block Retry) |
| `tool()` / `ToolSpec` (`ze_agents/tool.py:198,374`), `render_tool` (`ze_components/tools.py:187`), `show_*` (`ze_priority/compose/tools.py:31,47,63`) | registry | `produces_ui` flag; set on render and show tools |
| `format_procedure_guidance` (`procedures/discovery.py:119`), `validate_candidate` (`procedures/validate.py`), `invoke_procedure` (`procedures/tools.py:36`) | procedure discovery and admission | one-line script guidance; `tool_script` evidence rule; script-procedure reply |
| `docker-compose.yml` workspace service | local dev | `cap_add: [NET_ADMIN]` |
| `CostTracker.record` (`telemetry/tracker.py`) | client | also charges the active script budget (ContextVar from ze-agents) |
| `ProcedureMatch` (`ze_memory/procedures/types.py:226`), discovery (`procedures/discovery.py:73,97`) | `match_skills`/procedure discovery, `invoke_procedure` | gains `source_kind` |
| `ProcedureSourceKind` (`procedures/types.py:12`) | admission, sources | gains `TOOL_SCRIPT` |
| `ActionRecorder.record_action`, `ActionContext` (`ze_memory/action_records/recorder.py:29-60`, `types.py:104`) | every producer | one row per script run (`source_record_id` = script id, so the idempotency key is unique); `ActionContext.script_key` added (JSONB, no migration); store gains `list_by_script_key` |
| `sidecar/workspace/main.py`, `supervisor.py`, `Dockerfile` | the sidecar | new `WS /scripts`, script slot, `zescript` user, nft drop rule |
| `ToolsTimeline.tsx` | trace module | script row with source and nested calls |
| eval `scoring.py`, scenario model | eval runner | `max_llm_calls` assertion |

## Design

Revised after Gauge's review of 2026-10-18 (M-1..M-7, Me-1..Me-5, N-1..N-7) and the user's answers to M-2 (scripts are a general harness capability, no opt-in list) and Me-4 (tool-signature key); see spec Clarifications.

### Contract (ze-agents `ze_agents/scripts.py`, `ze_agents/tool.py`)

- `SCRIPT_TOOL_NAME = "run_tool_script"`; `SCRIPT_TOOL_SCHEMA` (function schema: `source: string` optional, `procedure_id: string` optional, exactly one required, described in the schema text).
- `@dataclass(frozen=True) ScriptLimits(wall_seconds: int = 30, max_inner_calls: int = 20, max_proposed_writes: int = 10, max_spend_usd: float = 0.05, max_result_chars: int = 4000, max_source_chars: int = 8000, max_request_bytes: int = 262144, max_reply_bytes: int = 1048576, inner_result_store_chars: int = 2000)`, `from_config(config)` reading `workspace.scripts` with per-field fallback. Ten proposed writes: enough for a batch action, small enough that one confirmation lists them all (N-4).
- `ScriptRequest(seq: int, tool: str, args: dict)`; `ScriptOutcome(status: Literal["ok", "exception", "timeout", "killed", "bad_request", "busy", "unavailable", "resource_limit"], value: Any, writes: list[dict], stderr_tail: str, exception: str | None)`.
- `class ScriptRunner(Protocol)`: `async def run(self, *, script_id: str, agent: str, source: str, stub: str, limits: ScriptLimits, dispatch: Callable[[ScriptRequest], Awaitable[DispatchReply]]) -> ScriptOutcome`. `DispatchReply(ok: bool, value: Any = None, error: str | None = None, stop: bool = False)`.
- `ScriptBudget`, `current_script_budget: ContextVar[ScriptBudget | None]`, `charge_script(usd)`; `in_script_call: ContextVar[bool]` (set by the dispatcher around each inner `call_tool`, read by `ToolCallCapHook`).
- `SCRIPT_GUIDANCE` (appended to the system prompt once, before the loop, when the script tool is visible at the first iteration; harmless if later narrowing hides it): when to write a script (three or more reads, loops, joins, counting); print nothing (stdout is discarded); return only what the answer needs with `finish(...)`; propose writes with `propose(...)` in `finish`; tool results are JSON data, so inspect keys defensively; the error you get back shows the shape of the last result.
- `ScriptError(ZeError)` with `kind`.
- `ToolSpec.produces_ui: bool = False` and `@tool(produces_ui=...)` in `tool.py`: marks tools whose effect is drawing on screen (Me: M-2a). `render_tool` in ze-components sets it on every render tool; the three `show_*` compose tools in ze-priority declare it. A UI tool is never a "data read".
- `ToolSpec.egress: bool = False` and `@tool(egress=...)` (Gauge R-1, Maestro decision): marks READ tools that reach a caller-chosen URL or host (`browser_extract` in ze-browser today; T001 lists any other). An egress tool is never in the stub, so scripts keep their no-network property. A registry sweep fails when a READ tool has a URL-like parameter (`url`, `uri`, `link`, `host`, `endpoint`, `domain`) without `egress` or an explicit exemption with a reason.

### Stub and source helpers (ze-agents `ze_agents/script_stub.py`, pure)

- `build_stub(schemas: list[dict]) -> str`: one Python function per tool schema: keyword-only parameters from `properties` (required ones without default, others `= None`), JSON types mapped to annotations (`string→str`, `integer→int`, `number→float`, `boolean→bool`, `array→list`, `object→dict`), the description as docstring, body `return _call("<name>", {<non-None kwargs>})`. Plus `propose(tool: str, **args) -> dict` and `finish(result, writes=None)`. Names that are not valid identifiers are skipped. Deterministic output (sorted by tool name).
- `normalize_source(source) -> str` (comments, blank lines and trailing whitespace stripped through `tokenize`; literals kept) and `source_hash(source)`: used for the trace and the candidate name, not as the learning key.
- `tool_signature(agent: str, inner_tool_names: list[str]) -> str`: sha256 hex of `agent` plus the ordered list of distinct inner tool names in first-call order (Me-4, user answer).

### Loop integration (ze-agents `base_agent.py`, `ze_agents/script_step.py`, `ze_agents/delegate.py`, `ze_agents/nested_tools.py`, `ze_agents/tool_cap_hook.py`)

- Data-read set = `_visible_tool_names(ctx, names)` minus server tools, `delegate_to_agent`, `run_tool_script`, `invoke_procedure`, names starting `workspace_`, every tool with `access is ToolAccess.WRITE`, every tool with `produces_ui` (M-2a), and every tool with `egress` (R-1). FR-003 calls this "data read tools".
- Visibility (no opt-in, user answer to M-2): `run_tool_script` is added to `names` before the loop (like `_PROCEDURE_INVOKE_TOOL` at `base_agent.py:759`) whenever `ctx.script_runner` is set; per iteration it is sent only while the data-read set has at least one tool; its schema is substituted in the `tool_schemas` comprehension (like `DELEGATE_TOOL_SCHEMA`). `_visible_tool_names` keeps it through skill narrowing and through procedure narrowing (an explicit rule added beside the `invoke_procedure` one at `base_agent.py:298-310`), because the stub only ever holds narrowed tools (Me-3).
- `run_script_step(agent, args, ctx, call_id, deps) -> ScriptStepResult` in `script_step.py`:
  1. Resolve the source: `source`, or for `procedure_id` the READY match in `ctx.procedure_matches` with `source_kind == "tool_script"` (`steps[0]`); otherwise `procedure_not_script`.
  2. Over `max_source_chars` → `source_too_long` (no run).
  3. Build the data-read set and the stub from `_hide_deps(get_tool(n).llm_schema(), deps)`.
  4. Call `ctx.script_runner.run(...)` with a dispatcher. Per request the dispatcher validates the shape (`tool: str`, `args: dict`, else `bad_request`), then: refuses a name outside the set (`writes_must_be_proposed` when it is a write tool the agent has, else `tool_not_available`); refuses after `max_inner_calls` (`limit: inner_calls`, `stop=True`); refuses when the budget is spent (`limit: spend`, `stop=True`); otherwise sets `current_script_budget` and `in_script_call` for the duration of `agent.call_tool(name, ctx, _iteration=..., _lm_args=args, _call_id=uuid4().hex, **_merge_deps(name, _model_args(name, args), {**deps, "ctx": ctx}))` (N-1: the budget is set only in the dispatcher; a single inner call can overshoot it, and the check runs before the next call). The reply value (Me-2): a `str` result that parses as JSON to a dict or list is sent parsed (`tool_payload` rules); other results are encoded with `json.dumps(default=_encode)` where `_encode` gives `isoformat()` for dates and times, `str()` for UUIDs, Decimals and anything else, so dicts stay dicts; a failed call replies `ok: false` with the tool error. A reply over `max_reply_bytes` replies `result_too_large`. The stored inner `ToolCall.result` is cut to `inner_result_store_chars` (M-6); the reply to the script is separate. Requests are served one at a time in arrival order.
  5. Build the step `ToolCall(tool_name="run_tool_script", args={"procedure_id"} or {"source_hash"}, result=<model text>, script={...}, inner_calls=[...])`. Model text: on `ok`, the JSON of `value` capped at `max_result_chars` with `[truncated]`; otherwise the structured error JSON (`kind`, `message`, `completed` = [{name, success}], `stderr_tail` last 20 lines, and on `exception` `last_result_shape`: the type and up to 20 top-level keys or the first element's keys of the last successful inner result, Me-2).
  6. Validate proposed writes (N-3): each must be `{tool: str, args: dict}`; at most `max_proposed_writes`; each must be a WRITE tool in the agent's visible set; others become `ToolCall(success=False, error="not_a_proposable_write", parent_call_id=...)`.
- Proposed writes in `agentic_loop` (M-4): the script branch runs before the iteration's other calls are handled. Each proposal becomes a synthetic call with id `f"{tc_id}_w{i}"` passed through `_safe_call_id` (characters outside `[A-Za-z0-9_-]` replaced by `_`, cut to 64), appended to `messages[-1]["tool_calls"]` (the assistant message already in the transcript) and to the iteration's pending list, all before any call in the iteration can raise `LoopParked`, so the checkpointed `ParkedLoop.messages` holds them and `_apply_resume` finds a parked proposal by its `call_id`. The existing write path (retry refusal, constraint veto, park, round cap, approval, undo) handles each; the resulting `ToolCall` gets `parent_call_id`.
- Tool-call cap (M-5): `ToolCallCapHook.on_tool_start` does not count a call while `in_script_call` is set; the script's own `max_inner_calls` bounds those. Proposed writes run outside the dispatcher, so they count normally. (The hook's per-loop reset is existing behavior and unchanged.)
- `run_delegate` copies `ctx.script_runner` into `sub_ctx`.
- `flatten_tool_calls` (Me-1) becomes depth-first: each call, then (for a script step) its `inner_calls` in order with `parent_call_id`, then the next call; payload nesting (`result["tool_calls"]`) is skipped for script steps and their inner calls, so script-authored JSON can never become a `ToolCall` row for the honesty guards.

### Runner (ze-workspace `ze_workspace/scripts.py`, `ze_workspace/bootstrap.py`)

- `WorkspaceScriptRunner(client: WorkspaceClient, learning: ScriptLearning | None)` implements `ScriptRunner`: checks `/stat` (`scripts_isolated` true, else `unavailable` without connecting); opens `ws(s)://<sidecar>/scripts` with the bearer token (`websockets` client, `max_size` = 2 MiB); sends `start`; relays `call` frames to `dispatch` and sends `reply`; on `stop` sends `cancel`; on `end` returns `ScriptOutcome`. A Ze-side timeout of `wall_seconds + 5` cancels and returns `timeout`. Connection refused → `unavailable`; `busy` end → `busy` (N-2: parallel subtasks that both script get `sandbox_busy` and may answer without a script).
- After the run (any outcome), `ScriptLearning.record(...)` fire-and-forget.
- `WorkspaceStack` gains `script_runner: WorkspaceScriptRunner | None`; `build_workspace_stack` gains `procedure_admission: Any = None` and builds the runner (with learning when both the action store and admission service are given) when the sidecar is configured. The container (`ze_api/wiring/container.py`, lead) passes the admission service and puts `stack.script_runner` into `_build_config` (Me-5).

### Sidecar (`sidecar/workspace/scripts.py`, `script_runtime/`, `main.py`, `supervisor.py`, `Dockerfile`; `docker-compose.yml`)

- `WS /scripts`: refuses when `WORKSPACE_API_TOKEN` is empty (fail closed for this route only) and checks the bearer token before accept, raising `WebSocketException(code=1008)` (M-7). One script slot (`ScriptSlot`, separate from `RunJournal`); a second connection gets `end` with `busy`.
- On `start`: create `/tmp/ze-scripts/<id>` (owner `zescript`, 0700); write `ze_tools.py` (`script_runtime/ze_tools_base.py` + the stub), `main.py` (the source) and `_ze_main.py`; spawn `python3 -I -X utf8 _ze_main.py` as `zescript` with `cwd` = scratch. `-I` is for environment hygiene; `_ze_main.py` inserts the scratch dir at `sys.path[0]` so `import ze_tools` works (M-7; the uid is the boundary, not the import path). Env = `PATH`, `HOME=<scratch>`, `LANG`, `ZE_REQ_FD`, `ZE_REP_FD`. stdout → `DEVNULL`; stderr drained into a 64 KB ring (M-6). Two pipes: requests out, replies in.
- Resource limits in the preexec (M-6), beside setuid: `RLIMIT_AS` 256 MiB, `RLIMIT_NPROC` 32, `RLIMIT_FSIZE` 16 MiB, `RLIMIT_CPU` `wall_seconds + 1`, `RLIMIT_NOFILE` 64. The scratch dir over 32 MiB at end → `resource_limit`. A child killed by a limit signal (SIGKILL/SIGXCPU/SIGXFSZ, or MemoryError in stderr) ends `resource_limit`.
- `script_runtime/_ze_main.py`: first runs the isolation probe as `zescript` (M-7): `os.listdir("/workspace")` must raise `PermissionError` and a TCP connect to `1.1.1.1:53` with a 0.5 s timeout must fail; on any breach it writes `{"isolation_breach": "<what>"}` and exits; the sidecar ends the script `unavailable` and sets `scripts_isolated` false. Then it runs `main.py` with `runpy`. `ze_tools_base.py` defines `_call` (one JSON line `{"seq", "tool", "args"}` to the request fd, blocks on one reply line, raises `ToolError(message)` on `ok: false`), `finish` (`{"finish": value, "writes": [...]}`) and `propose` (returns `{"tool": ..., "args": {...}}`). Without `finish` the value is `None`.
- Relay and caps (M-6): a request line over `max_request_bytes`, malformed JSON, or a `finish` line over `max_reply_bytes` ends the script `bad_request`; more than `2 × max_inner_calls` request lines end it `bad_request`; the sidecar validates the `writes` shape before relaying `end`. WS `max_size` 2 MiB on the sidecar.
- The scratch size is polled during the run (the relay loop's 0.1 s tick); over 32 MiB kills the script as `resource_limit` (R-2).
- End, cancel and timeout kill every process of the `zescript` uid (iterate `/proc` for that uid and SIGKILL), not only the process group, so a `setsid` child cannot outlive the script (M-6). Then delete the scratch dir.
- Isolation at startup (M-7): the lifespan sets `/workspace` to mode 0750 at runtime (the volume mount masks the image's mode), after `apply_network_isolation`. `apply_network_isolation` adds a `reject` rule for all output from `zescript`'s uid (nft `meta skuid`, iptables `--uid-owner` fallback) and verifies it by listing the chain and finding the rule (not by exit codes). `scripts_isolated` = rule verified and mode set; the per-script probe can only lower it. The workspace uid could chmod `/workspace` back; the per-script probe catches that. AF_UNIX: the sidecar exposes no unix socket to that uid (recorded in the ADR).
- `docker-compose.yml`: `cap_add: [NET_ADMIN]` on the workspace service, so local dev isolates; without it `scripts_isolated` is false and scripts are unavailable (the docs say so).
- Tests run through the existing `make test-workspace-sidecar` target (`sidecar/workspace/tests/`); no new target (Me-5).

### Learning (ze-workspace `ze_workspace/script_learning.py`; ze-memory)

- One action record per run (M-1), copying the pattern of `ze_workspace/action_records.py`: `producer_kind="workspace"`, `source_record_type="tool_script"`, `source_record_id=<script_id uuid>` (so the idempotency key is unique per run), `action_kind="run"`, lifecycle `SUCCEEDED`/`FAILED`/`TIMED_OUT` with outcome `SUCCESS`/`FAILURE`/`TIMEOUT` and a `failure_code` from the outcome status, `actor` = the agent, summary `"Script by <agent>: <n> tool calls"`, and `ActionContext.script_key = tool_signature(...)`. `_context_to_json` and the row reader in `action_records/store.py` are explicit field lists: `script_key` is added to both.
- ze-memory: `ActionContext.script_key: str | None = None` (stored in the existing `context` JSONB; no migration) and `ActionRecordStore.list_by_script_key(script_key, limit=3)` (newest first; unindexed, a handful of rows per key). The authoritative ref is the recorder's own (`workspace.tool_script` + script id).
- On a success without `procedure_id`: the last three records for the key all `SUCCEEDED` and `candidate_exists(<that name>)` false → submit `ProcedureCandidate(source_kind=TOOL_SCRIPT, provenance=..., name=f"Script: {' → '.join(tools)} [{script_key[:8]}]"` (cut to 120 chars; deterministic per key, so the reviewer in Mind › Procedures sees what it does without reading the source, R-5), trigger=<first 120 chars of the user turn>, preconditions=[], steps=[<this run's source>], success_criteria=["script ends ok"], limits=<ordered inner tool names>, evidence_refs=[the three action record ids])` (the latest successful source, Me-4 user answer).
- ze-memory procedures (Me-3): `ProcedureSourceKind.TOOL_SCRIPT`; `validate_candidate` requires `evidence_refs` and `len(steps) == 1` with `len(steps[0]) <= 8000` for `tool_script`; `ProcedureMatch.source_kind` filled inside `list_active_versions` (one LEFT JOIN `procedure_versions.admission_id → procedure_admissions.candidate_id → procedure_candidates.source_kind`, no extra query per match); `candidate_exists(name)`. `format_procedure_guidance` prints a `tool_script` match as one line, `- [ready] <name> id=<id>: script procedure, run it with run_tool_script(procedure_id="<id>")`, never its steps. `invoke_procedure` on a script procedure records the invocation as today and returns `"This is a script procedure: run it with run_tool_script(procedure_id=...)."`.

### Spend attribution (ze-core)

- `CostTracker.record` estimates the call's cost with the static price table (`telemetry/pricing.py`; unknown models priced at its conservative default, N-1) and calls `ze_agents.scripts.charge_script(usd)`; the budget ContextVar is set only while the dispatcher runs an inner call.

### Trace and surfaces

- `_extract_tool_calls` (M-3) sets `access="script"` for `run_tool_script` (a name branch beside `delegate`) and copies `parent_call_id` and `script`. `ToolCallTrace` gains `parent_call_id: str | None` and `script: ScriptTrace | None`.
- `retry_eligibility` treats `access == "script"` as read (the step itself changes nothing; its proposed writes are their own rows with their own access). `ToolCallTraceResponse.access` and the generated client's access union gain `"script"`; the web treats it like `delegate` for styling.
- Web `ToolsTimeline.tsx`: a row with `script` set draws "Script · <outcome> · <n> calls · <duration>" and expands to the source (monospace, scrollable, "cut" note) and its child rows (`parent_call_id`); a limit shows as the outcome text. Pure grouping helper `widgets/assemble/lib/script-rows.ts`. Tests in the existing `widgets/assemble/ui/trace/instruments.test.tsx` (Me-5).

### Agents

- No per-agent change: the capability lives in `BaseAgent`. Any agent with a data read tool (for example calendar, messenger and finance) gets the script tool when a runner is wired; T001 lists, per registered agent, whether it has a data read tool. Build T001 found the companion's one data read, `get_briefing`, so it gets the script tool too (accepted under the user's rule); research, priority, ingestion and prospecting have none. Cross-agent reads for the companion are the follow-up read-bridge phase. `refresh_news` (news) is a READ that fetches the user's configured feeds, not a caller-chosen URL, so it is not `egress`. No prompt edits.
- Finance is pinned to one provider; a script's source and value go only to the same model and the trace, so nothing leaves that provider (N-5, ADR).

### Eval

- Scenario field `max_llm_calls: int`; `scoring.py` fails the scenario when the run's `llm_calls` (already computed in `metrics.py`) exceeds it.
- `eval/scenarios/tool_scripts.yaml`, three multi-step read scenarios: finance ("what did I spend by merchant this month; top five"), messenger ("which unread emails are from people I emailed last week"), calendar ("how many hours of meetings do I have each day next week, and which day is lightest"); `expected_tools: [run_tool_script]`, `max_llm_calls: 3`; criteria on the answer. Live only with the user's OK.

### Config

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

(The byte caps and `inner_result_store_chars` are code constants in `ScriptLimits`, not config.)

### Docs

- ADR `specs/arch/programmatic-tool-use.md`: Ze-initiated channel; no sandbox credential; no network (reject rule verified at startup, per-script probe; egress tools such as `browser_extract` excluded from the stub, so a script cannot reach the network through a tool either); resource limits; stub = data-read tools (UI and egress tools excluded); inner calls are ordinary calls (counted by the script cap, not the turn cap); proposed writes; why a hosted sandbox is refused; learning through the ledger by tool signature; AF_UNIX note; finance provider pin.
- `docs/architecture.md`: the script path (a short sequence; consider a diagram per the docs rule).
- `docs/configuration.md`: `workspace.scripts`.
- `docs/sdk.md`: scripts as a harness capability (no opt-in); `produces_ui`; how a tool appears in `ze_tools` (schema-derived signature, JSON return); write tools must be proposed.
- `docs/adding-an-agent.md`: every agent with a data read tool gets scripts; mark screen-drawing tools `produces_ui`.
- `docs/workspace.md`: scripts run beside workspace runs, no network, scratch only, resource limits; compose `cap_add: [NET_ADMIN]`; unavailable in dev without it (N-6).
- `docs/eval.md`: the `max_llm_calls` scenario field.
- `sidecar/workspace/README.md`: `WS /scripts`, frames and caps, the `zescript` user, rlimits, the script slot, `scripts_isolated` and the probe.
- `core/ops/ze-workspace/README.md` (runner lane): the script runner and learning modules; `AGENTS.md` (layout lines for `ze_agents/scripts.py`, `script_stub.py`, `script_step.py`, `ze_workspace/scripts.py`, `script_learning.py`; phase row; Learned Workspace Fact); `specs/README.md` row.

### Risks

- Learning may still fire rarely: the tool signature is loose on purpose, and every candidate goes through review in Mind › Procedures before use (Me-4).
- The script runs model-written code without asking; the boundary is the uid with no network, no `/workspace`, rlimits and a verified rule, re-probed per script.

## Project Structure

```text
core/contracts/ze-agents/ze_agents/scripts.py           (new, contract)
core/contracts/ze-agents/ze_agents/script_stub.py       (new, pure)
core/contracts/ze-agents/ze_agents/script_step.py       (new)
core/contracts/ze-agents/ze_agents/{base_agent,nested_tools,delegate,tool_cap_hook}.py
core/contracts/ze-agents/ze_agents/{types,tool}.py      (ToolCall, AgentContext, produces_ui)
core/kernel/ze-components/ze_components/tools.py        (render tools produce UI)
core/arbitration/ze-priority/ze_priority/compose/tools.py (show_* produce UI)
core/engine/ze-core/ze_core/conversation/messages/types.py
core/engine/ze-core/ze_core/conversation/retry.py
core/engine/ze-core/ze_core/orchestration/nodes/{trace,execution}.py
core/engine/ze-core/ze_core/telemetry/tracker.py
core/ops/ze-workspace/ze_workspace/{scripts,script_learning}.py   (new)
core/ops/ze-workspace/ze_workspace/{client,bootstrap}.py
core/ops/ze-workspace/pyproject.toml                    (websockets)
core/cognition/ze-memory/ze_memory/procedures/{types,store,discovery,validate,tools}.py
core/cognition/ze-memory/ze_memory/action_records/{types,store}.py
sidecar/workspace/{main,supervisor,scripts}.py, script_runtime/, Dockerfile, requirements.txt, tests/, README.md
docker-compose.yml                                      (cap_add NET_ADMIN)
apps/ze-api/ze_api/wiring/container.py
apps/ze-api/ze_api/api/v0/messages/schemas.py, api/ws/schemas.py, interface/native.py
apps/ze-api/config/config.yaml
packages/ze-client/                                     (regenerated)
apps/ze-web/src/widgets/assemble/ui/trace/{ToolsTimeline.tsx,instruments.test.tsx}, widgets/assemble/lib/script-rows.ts
core/ops/ze-eval/ze_eval/{scenario,scoring}.py, eval/scenarios/tool_scripts.yaml
specs/arch/programmatic-tool-use.md, docs/*.md, AGENTS.md, specs/README.md
```

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first): `ze_agents/scripts.py` (types, Protocol, budget and `in_script_call` ContextVars, guidance, error) with its tests; `ToolSpec.produces_ui` and `ToolSpec.egress` with their `@tool(...)` parameters; the `ToolCall` fields (`parent_call_id`, `inner_calls`, `script`) and `AgentContext.script_runner`; `ActionContext.script_key`; `ToolCallTrace`, `ScriptTrace` and the `"script"` access value; REST and WS schema fields and the regenerated client; `ProcedureSourceKind.TOOL_SCRIPT` and `ProcedureMatch.source_kind`; the `workspace.scripts` config block; the sidecar WS frame contract as a shared test fixture (`core/ops/ze-workspace/tests/fixtures/script_frames.py`); `script_runner` in `_build_config` with a `None` placeholder until T031.

| Lane | Model / role | Owns (files and dirs, disjoint) | Tasks | Starts after | Reviewer |
|------|--------------|---------------------------------|-------|--------------|----------|
| lead | Sonnet ENG lead | `ze_agents/scripts.py` + test, `ze_agents/tool.py`, `ze_agents/types.py`, `ze_memory/action_records/types.py`, `conversation/messages/types.py`, `api/v0/messages/schemas.py`, `api/ws/schemas.py`, `interface/native.py`, `packages/ze-client`, `procedures/types.py`, `config.yaml`, `ze_api/wiring/container.py`, `ze-workspace/tests/fixtures/script_frames.py`; integration, ADR, final gates | T001–T008, T031, T034, T035 | - | Gauge |
| harness | Sonnet ENG | `ze_agents/script_step.py`, `ze_agents/base_agent.py`, `ze_agents/nested_tools.py`, `ze_agents/delegate.py`, `ze_agents/tool_cap_hook.py`, `orchestration/nodes/execution.py`, `orchestration/nodes/trace.py`, `conversation/retry.py`, `telemetry/tracker.py`, their tests (ze-agents `test_script_step.py`, `test_base_agent_loop.py`, `test_agentic_loop_park.py`, `test_delegate.py`, `test_tool_cap_hook*.py`, nested-tools tests; ze-core `test_message_trace.py`, retry, execution and tracker tests) | T010–T017, T026 | contract step | Gauge |
| stub | Haiku JR | `ze_agents/script_stub.py`, `ze-agents/tests/test_script_stub.py` | T009 | contract step | Gauge |
| sandbox | Sonnet ENG | `sidecar/workspace/**` (`main.py`, `supervisor.py`, `scripts.py`, `script_runtime/`, `Dockerfile`, `requirements.txt`, `tests/`, `README.md`), `docker-compose.yml` | T018–T022 | contract step | Gauge |
| runner | Sonnet ENG | `ze_workspace/scripts.py`, `ze_workspace/script_learning.py`, `ze_workspace/client.py`, `ze_workspace/bootstrap.py`, `ze-workspace/pyproject.toml`, `core/ops/ze-workspace/README.md`, their tests; `procedures/store.py`, `procedures/discovery.py`, `procedures/validate.py`, `procedures/tools.py`, `action_records/store.py` and their tests | T023–T025, T027 | contract step (T007 frame fixture) | Gauge |
| flags | Haiku JR | `ze_components/tools.py` (`render_tool` sets `produces_ui`), `ze_priority/compose/tools.py` (`show_*` declare it), `integrations/ze-browser/ze_browser/tool.py` (`browser_extract` declares `egress`), their tests, new `apps/ze-api/tests/test_tool_egress_flags.py`, `ze_eval/scenario.py`, `ze_eval/scoring.py`, ze-eval tests, `eval/scenarios/tool_scripts.yaml` | T028–T030 | contract step | Gauge |
| web | Sonnet ENG | `widgets/assemble/ui/trace/ToolsTimeline.tsx`, `widgets/assemble/ui/trace/instruments.test.tsx`, `widgets/assemble/lib/script-rows.ts` + test | T032–T033 | contract step | Gauge |
| docs | Haiku DOCS | `docs/architecture.md`, `docs/configuration.md`, `docs/sdk.md`, `docs/adding-an-agent.md`, `docs/workspace.md`, `docs/eval.md`, `AGENTS.md`, `specs/README.md` | T036 | all lanes merged | Gauge |

**Rules**: one lane per file; shared files belong to `lead` and other lanes request changes; each lane works on a sub-branch of the floor branch and `lead` merges harness → stub → sandbox → runner → flags → web → docs; the sidecar README is the sandbox lane's; the ADR is the lead's; design and cross-layer work stays on Sonnet; the JR lanes get only tasks whose tests are written into the task.

## Complexity Tracking

None.
