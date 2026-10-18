# Implementation Plan: Programmatic Tool Use

**Branch**: `197-programmatic-tool-use` | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/197-programmatic-tool-use/spec.md` (clarified 2026-10-18).

## Summary

An opted-in agent sees one harness tool, `run_tool_script`, handled in the agentic loop like `delegate_to_agent` (not a registry tool). The loop builds the agent's visible read-tool set, generates a Python stub from those tools' schemas, and hands source, stub and limits to a `ScriptRunner` (a Protocol in ze-agents, implemented in ze-workspace, wired by ze-api into the turn config). The runner opens a WebSocket to the sidecar; the sidecar runs the script as a no-network sandbox user in a throwaway directory and relays each framed request from a dedicated pipe. For each request the loop's dispatcher checks the name against the visible read set, the limits and the spend budget, then calls `call_tool` as the agent, so every gate, hook, cap and undo rule applies unchanged. The script's return value (capped) goes to the model; proposed writes run after the script as ordinary tool calls in the same loop iteration, so parking and confirmation reuse the 181 path. Each script step is a `ToolCall` holding its inner calls; the trace flattens them with `parent_call_id`. Every finished script is an action record keyed by its normalized source hash; three successes in a row submit one procedure candidate (`tool_script` source kind), and `run_tool_script(procedure_id=...)` reruns a validated script procedure with the stub built from the agent's tools at that moment.

**Build order**: after 187b lands (`ToolCall.call_id`, `started_at`, the per-call timing and the turn recorder used for spend attribution). Independent of 196.

## Technical Context

**Language/Version**: Python 3.12 (backend and sidecar), TypeScript 5 / React 19 (web)

**Primary Dependencies**: FastAPI WebSocket on the sidecar (uvicorn[standard] already installed), `websockets==16.0` (already pinned in ze-api) added to ze-workspace for the client, nftables in the sidecar image (already installed)

**Storage**: none new. Script steps live on `messages.trace` JSON; script runs are `action_records` rows (`source_record_type = "tool_script"`, existing table); procedure candidates use the existing `procedure_*` tables (`source_kind` is unconstrained TEXT, so `tool_script` needs no migration; verified in `zm022`). No migration.

**Testing**: pytest with a fake `ScriptRunner` for loop and gate tests; sidecar relay tests in a new `sidecar/workspace/tests/` (run with `make test-sidecar`; uid switching and nft checks marked `docker`, run by the quickstart smoke test); vitest for the trace row; `eval/scenarios/tool_scripts.yaml` with a `max_llm_calls` assertion (live only with the user's OK).

**Target Platform**: ze-api and the workspace sidecar on Fly; ze-web SPA.

**Performance Goals**: script start (WS open to first request served) under 1 s on the sidecar; an inner read adds no model call.

**Constraints**: the sandbox never reaches Ze; no inner call bypasses `call_tool`; telemetry and learning never fail a turn; limits from config (`workspace.scripts`).

**Scale/Scope**: one script at a time per sidecar; up to 20 inner calls per script; four agents opted in.

## Constitution Check

| Principle | Status |
|---|---|
| I Spec first | Spec clarified 2026-10-18; ADR `specs/arch/programmatic-tool-use.md` in this phase |
| II Single user | One script slot; no tenancy |
| III Layered packages | Contract and dispatch in ze-agents (imports nothing from ze-workspace); runner in ze-workspace (already depends on ze-agents, ze-memory); wiring in ze-api; plugins only flip `script_tools = True` |
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
| `CostTracker.record` (`telemetry/tracker.py`) | client | also charges the active script budget (ContextVar from ze-agents) |
| `ProcedureMatch` (`ze_memory/procedures/types.py:226`), discovery (`procedures/discovery.py:73,97`) | `match_skills`/procedure discovery, `invoke_procedure` | gains `source_kind` |
| `ProcedureSourceKind` (`procedures/types.py:12`) | admission, sources | gains `TOOL_SCRIPT` |
| `ActionRecordStore.list` (`action_records/store.py:42`) | ledger readers | used with `authoritative_ref=AuthoritativeRef("tool_script", <hash>)`; no change |
| `sidecar/workspace/main.py`, `supervisor.py`, `Dockerfile` | the sidecar | new `WS /scripts`, script slot, `zescript` user, nft drop rule |
| `ToolsTimeline.tsx` | trace module | script row with source and nested calls |
| eval `scoring.py`, scenario model | eval runner | `max_llm_calls` assertion |

## Design

### Contract (ze-agents `ze_agents/scripts.py`)

- `SCRIPT_TOOL_NAME = "run_tool_script"`; `SCRIPT_TOOL_SCHEMA` (function schema: `source: string` optional, `procedure_id: string` optional, exactly one required, described in the schema text).
- `@dataclass(frozen=True) ScriptLimits(wall_seconds: int = 30, max_inner_calls: int = 20, max_spend_usd: float = 0.05, max_result_chars: int = 4000, max_source_chars: int = 8000)`, `from_config(config)` reading `workspace.scripts` with per-field fallback.
- `ScriptRequest(seq: int, tool: str, args: dict)`; `ScriptOutcome(status: Literal["ok", "exception", "timeout", "killed", "bad_request", "busy", "unavailable"], value: Any, writes: list[dict], stderr_tail: str, exception: str | None)`.
- `class ScriptRunner(Protocol)`: `async def run(self, *, script_id: str, source: str, stub: str, limits: ScriptLimits, dispatch: Callable[[ScriptRequest], Awaitable[DispatchReply]]) -> ScriptOutcome`. `DispatchReply(ok: bool, value: Any = None, error: str | None = None, stop: bool = False)` (`stop=True` tells the runner to cancel the script after sending the reply).
- `ScriptBudget` and `current_script_budget: ContextVar[ScriptBudget | None]`; `charge_script(usd: float)` adds to the active budget (no-op without one).
- `SCRIPT_GUIDANCE`: a short system-prompt paragraph the loop appends when the script tool is visible (when to write a script: three or more reads, loops, joins; return only what the answer needs; propose writes in the return value; available functions are in `ze_tools`).
- `ScriptError(ZeError)` with `kind`.

### Stub and source helpers (ze-agents `ze_agents/script_stub.py`, pure)

- `build_stub(schemas: list[dict]) -> str`: one Python function per tool schema: keyword-only parameters from `properties` (required ones without default, others `= None`), JSON types mapped to annotations (`string→str`, `integer→int`, `number→float`, `boolean→bool`, `array→list`, `object→dict`), the description as docstring, body `return _call("<name>", {<non-None kwargs>})`. Plus `propose(tool: str, **args) -> dict` and `finish(result, writes=None)`. Names that are not valid identifiers are skipped. Deterministic output (sorted by tool name).
- `normalize_source(source) -> str`: strip comments and blank lines and trailing whitespace through `tokenize`, keep literals; `source_hash(source) -> str`: sha256 hex of the normalized text.

### Loop integration (ze-agents `base_agent.py`, `ze_agents/script_step.py`)

- `BaseAgent.script_tools: bool = False`.
- The script tool is visible when `self.script_tools`, `ctx.script_runner` is set, and the visible read set (below) has at least two tools. It survives skill and procedure narrowing (like `invoke_procedure`), because the stub only ever holds narrowed tools.
- Visible read set = `_visible_tool_names(ctx, names)` minus server tools, `delegate_to_agent`, `run_tool_script`, `invoke_procedure`, names starting `workspace_`, and every tool whose spec has `access is ToolAccess.WRITE`.
- `run_script_step(agent, args, ctx, call_id, deps) -> ScriptStepResult` in `script_step.py`:
  1. Resolve the source: `source`, or for `procedure_id` the READY match in `ctx.procedure_matches` with `source_kind == "tool_script"` (`steps[0]`); otherwise a structured error `procedure_not_script`.
  2. Over `max_source_chars` → error `source_too_long` (no run).
  3. Build the read set and the stub from `_hide_deps(get_tool(n).llm_schema(), deps)` for each name.
  4. Set `current_script_budget`; call `ctx.script_runner.run(...)` with a dispatcher that, per request: refuses a name outside the read set (`writes_must_be_proposed` when it is a write tool the agent has, else `tool_not_available`); refuses after `max_inner_calls` (`limit: inner_calls`, `stop=True`); refuses when the budget is spent (`limit: spend`, `stop=True`); otherwise calls `agent.call_tool(name, ctx, _iteration=..., _lm_args=args, _call_id=uuid4().hex, **_merge_deps(name, _model_args(name, args), {**deps, "ctx": ctx}))`, records the `ToolCall` with `parent_call_id`, and replies with the JSON-safe result (`_serialise_result` string for non-JSON values; `ok=False` with the tool error when `success` is false). Requests are handled one at a time in arrival order.
  5. Build the step `ToolCall(tool_name="run_tool_script", args={"procedure_id"} or {"source_hash"}, result=<model text>, script={"source": capped, "source_cut": bool, "outcome": status, "limit": name|None, "source_hash": h, "procedure_id": id|None}, inner_calls=[...])`. Model text: on `ok` the JSON of `value` capped at `max_result_chars` with `"[truncated]"` appended when cut; otherwise the structured error JSON (`kind`, `message`, `completed` = [{name, success}], `stderr_tail` last 20 lines).
  6. Return the proposed writes (`[{tool, args}]`, at most `max_inner_calls` minus used, each must be a WRITE tool the agent has visible; others become `ToolCall(success=False, error="not_a_proposable_write", parent_call_id=...)`).
- In `agentic_loop`, the script branch runs `run_script_step`, appends the step call, then appends each proposed write as a synthetic tool call `{"id": f"{tc_id}:w{i}", "name": tool, "arguments": args}` to the iteration's pending list, so the existing write path (retry refusal, constraint veto, park, round cap, approval, undo) handles it; the resulting `ToolCall` gets `parent_call_id = step call_id`. The tool message for the script call carries only the model text; each proposed write gets its own tool message as today (the assistant message lists the synthetic call ids so the transcript stays valid).
- `flatten_tool_calls` yields each script step, then its `inner_calls` (with `parent_call_id`) in order.

### Runner (ze-workspace `ze_workspace/scripts.py`)

- `WorkspaceScriptRunner(client: WorkspaceClient, recorder: ScriptLearning | None)` implements `ScriptRunner`: opens `ws(s)://<sidecar>/scripts` with the bearer token (`websockets` client), sends `start` (`id`, `source`, `stub`, `timeout_seconds = wall_seconds`), relays `call` frames to `dispatch` and sends `reply`; on `stop` sends `cancel`; on `end` returns `ScriptOutcome`. A Ze-side timeout of `wall_seconds + 5` cancels and returns `timeout`. Connection refused → `unavailable`; `busy` end → `busy`.
- After the run (any outcome), `ScriptLearning.record(...)` (below), fire-and-forget.
- `WorkspaceClient.scripts_url()` builds the WS URL from the existing base URL.

### Sidecar (`sidecar/workspace/scripts.py`, `main.py`, `supervisor.py`, `Dockerfile`)

- `WS /scripts` (bearer token checked before accept): one script slot (`ScriptSlot`, separate from `RunJournal`); a second connection gets `{"type": "end", "status": "busy"}` and is closed.
- On `start`: create `/tmp/ze-scripts/<id>` (owner `zescript`, 0700); write `ze_tools.py` (= `script_runtime/ze_tools_base.py` + the stub) and `main.py` (the source); spawn `python3 -I -X utf8 _ze_main.py` as `zescript` (setuid/setgid like the run path), env = `PATH`, `HOME=<scratch>`, `LANG`, `ZE_REQ_FD`, `ZE_REP_FD`; pass two pipes (requests out, replies in).
- `script_runtime/_ze_main.py` runs `main.py` with `runpy`; `ze_tools_base.py` defines `_call` (writes one JSON line `{"seq", "tool", "args"}` to the request fd, blocks on one reply line, raises `ToolError(message)` on `ok: false`), `finish` (writes `{"finish": value, "writes": [...]}`) and `propose`. A script that ends without `finish` returns `None` as its value.
- The sidecar relays request lines as `call` frames and `reply` frames back to the reply fd; malformed lines end the script with `bad_request`; more than `2 × max_inner_calls` lines end it with `bad_request` (backstop; Ze enforces the real cap).
- Wall time: kill the process group at `timeout_seconds` (`timeout`); `cancel` kills it (`killed`). On exit send `end` with status, value, writes, the last 20 stderr lines and the exception line; delete the scratch directory.
- Isolation: `Dockerfile` adds the system user `zescript` (no home in `/workspace`) and sets `/workspace` to mode 0750 so `zescript` cannot read it; `apply_network_isolation` adds a rule dropping all output from `zescript`'s uid (nft `meta skuid`, iptables `--uid-owner` fallback). Startup logs a warning, and `/stat` reports `scripts_isolated: false`, when the rule could not be applied; the Ze runner refuses to run scripts (`unavailable`) when `scripts_isolated` is false.

### Learning (ze-workspace `ze_workspace/script_learning.py`; ze-memory)

- `ScriptLearning(action_store, admission_service)`: `record(agent, source_hash, source, outcome, inner_tool_names, procedure_id)` appends an action record (`producer_kind="workspace"`, `source_record_type="tool_script"`, `source_record_id=source_hash`, `action_kind="run"`, outcome succeeded/failed, summary `"Script by <agent>: <n> tool calls"`).
- On a success without `procedure_id`: read the last three records for `AuthoritativeRef("tool_script", hash)`; when all three succeeded, they are by the same agent, and `candidate_exists(f"script:{hash[:12]}")` is false, submit `ProcedureCandidate(source_kind=TOOL_SCRIPT, provenance=..., name=f"script:{hash[:12]}", trigger=<first line of the user turn, ≤120 chars>, steps=[normalized source], success_criteria=["script ends ok"], limits=sorted(inner_tool_names), evidence_refs=[action_record ids])`.
- ze-memory: `ProcedureSourceKind.TOOL_SCRIPT = "tool_script"`; `ProcedureMatch.source_kind: str | None = None`. Source kind lives only on candidates, so `procedures/store.py` reads it for a version through `procedure_versions.admission_id → procedure_admissions.candidate_id → procedure_candidates.source_kind` (LEFT JOIN; NULL for versions without an admission), and `discovery.py` fills the match. `store.py` also gains `candidate_exists(name: str) -> bool` for the dedupe check.

### Spend attribution (ze-core)

- `CostTracker.record` estimates the call's cost with the existing static price table (`telemetry/pricing.py`) and calls `ze_agents.scripts.charge_script(usd)`; the ContextVar is only set while a script's dispatcher runs an inner call, so only model calls made by inner tools are charged.

### Trace and surfaces

- `ToolCallTrace` gains `parent_call_id: str | None` and `script: ScriptTrace | None` (`source`, `source_cut`, `outcome`, `limit`, `source_hash`, `procedure_id`). `_extract_tool_calls` copies them.
- `ToolCallTraceResponse` gains the same; the `trace_update` tool rows carry them; regenerate `@myguyze/ze-client`.
- Retry eligibility and the rollback plan already read the flattened list; inner reversible calls are proposed writes (top-level calls with `parent_call_id`), so they appear as today.
- Web `ToolsTimeline.tsx`: a row with `script` set draws "Script · <outcome> · <n> calls · <duration>" and expands to the source (monospace, scrollable, "cut" note) and its child rows (`parent_call_id`); a limit shows as the outcome text. Pure grouping helper `widgets/assemble/lib/script-rows.ts`.

### Agents

- `script_tools = True` on companion (`ze_personal/agents/companion/agent.py`), calendar (`ze_calendar/agents/calendar/agent.py`), messenger (`ze_messenger/agents/messenger/agent.py`), finance (`ze_finance/agents/finance/agent.py`). No prompt edits (the loop appends `SCRIPT_GUIDANCE`).

### Eval

- Scenario field `max_llm_calls: int`; `scoring.py` fails the scenario when the run's `llm_calls` (already computed in `metrics.py`) exceeds it.
- `eval/scenarios/tool_scripts.yaml`: two multi-step read scenarios (companion: "which of my open goals involve people I haven't contacted in a month"; calendar: "how many hours of meetings do I have each day next week, and which day is lightest"), `expected_tools: [run_tool_script]`, `max_llm_calls` set from the mocked baseline in T030; criteria on the answer. Live only with the user's OK.

### Config

```yaml
workspace:
  scripts:
    wall_seconds: 30
    max_inner_calls: 20
    max_spend_usd: 0.05
    max_result_chars: 4000
    max_source_chars: 8000
```

### Docs

- ADR `specs/arch/programmatic-tool-use.md`: Ze-initiated channel; no sandbox credential; no network for scripts; stub = visible read tools; inner calls are ordinary calls; proposed writes; why a hosted sandbox is refused; learning through the ledger.
- `docs/architecture.md`: the script path (a short sequence; consider a diagram per the docs rule).
- `docs/configuration.md`: `workspace.scripts`.
- `docs/sdk.md`: `script_tools = True`; how a tool appears in `ze_tools` (schema-derived signature, untyped return); write tools must be proposed.
- `docs/adding-an-agent.md`: the opt-in line.
- `docs/workspace.md`: scripts run beside workspace runs, no network, scratch only.
- `docs/eval.md`: the `max_llm_calls` scenario field.
- `sidecar/workspace/README.md`: `WS /scripts`, the `zescript` user, the script slot, `scripts_isolated`.
- `core/ops/ze-workspace/README.md` (runner lane): the script runner and learning modules; `AGENTS.md` (layout lines for `ze_agents/scripts.py`, `script_stub.py`, `script_step.py`, `ze_workspace/scripts.py`, `script_learning.py`; phase row; Learned Workspace Fact); `specs/README.md` row.

## Project Structure

```text
core/contracts/ze-agents/ze_agents/scripts.py           (new, contract)
core/contracts/ze-agents/ze_agents/script_stub.py       (new, pure)
core/contracts/ze-agents/ze_agents/script_step.py       (new)
core/contracts/ze-agents/ze_agents/base_agent.py
core/contracts/ze-agents/ze_agents/types.py             (ToolCall, AgentContext)
core/contracts/ze-agents/ze_agents/nested_tools.py
core/engine/ze-core/ze_core/conversation/messages/types.py
core/engine/ze-core/ze_core/orchestration/nodes/trace.py
core/engine/ze-core/ze_core/orchestration/nodes/execution.py
core/engine/ze-core/ze_core/telemetry/tracker.py
core/ops/ze-workspace/ze_workspace/scripts.py           (new)
core/ops/ze-workspace/ze_workspace/script_learning.py   (new)
core/ops/ze-workspace/ze_workspace/client.py
core/ops/ze-workspace/pyproject.toml                    (websockets)
core/cognition/ze-memory/ze_memory/procedures/{types,store,discovery}.py
sidecar/workspace/{main,supervisor,scripts}.py, script_runtime/, Dockerfile, requirements.txt, tests/
apps/ze-api/ze_api/wiring/container.py, ze_api/wiring/workspace*.py (runner construction)
apps/ze-api/ze_api/api/v0/messages/schemas.py, api/ws/schemas.py, interface/native.py
apps/ze-api/config/config.yaml
packages/ze-client/                                     (regenerated)
plugins/ze-personal/.../companion/agent.py, ze-calendar calendar agent, ze-messenger agent, ze-finance agent
apps/ze-web/src/widgets/assemble/ui/trace/ToolsTimeline.tsx, widgets/assemble/lib/script-rows.ts
core/ops/ze-eval/ze_eval/{scenario,scoring}.py, eval/scenarios/tool_scripts.yaml
Makefile (test-sidecar)
specs/arch/programmatic-tool-use.md, docs/*.md, sidecar/workspace/README.md, AGENTS.md, specs/README.md
```

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first): `ze_agents/scripts.py` (types, Protocol, budget ContextVar, guidance, error) with its tests; the `ToolCall` fields (`parent_call_id`, `inner_calls`, `script`) and `AgentContext.script_runner`; `ToolCallTrace` and `ScriptTrace`; REST and WS schema fields and the regenerated client; `ProcedureSourceKind.TOOL_SCRIPT` and `ProcedureMatch.source_kind`; the `workspace.scripts` config block; the sidecar WS frame contract as a shared test fixture (`core/ops/ze-workspace/tests/fixtures/script_frames.py`); `make test-sidecar`; `script_runner` in `_build_config` with a `None` placeholder until the runner lane wires it.

| Lane | Model / role | Owns (files and dirs, disjoint) | Tasks | Starts after | Reviewer |
|------|--------------|---------------------------------|-------|--------------|----------|
| lead | Sonnet ENG lead | `ze_agents/scripts.py` + test, `ze_agents/types.py`, `conversation/messages/types.py`, `api/v0/messages/schemas.py`, `api/ws/schemas.py`, `interface/native.py`, `packages/ze-client`, `procedures/types.py`, `config.yaml`, `Makefile`, `ze_api/wiring/*`, `ze-workspace/tests/fixtures/script_frames.py`; integration, ADR, final gates | T001–T008, T031, T034, T035 | - | Gauge |
| harness | Sonnet ENG | `ze_agents/script_step.py`, `ze_agents/base_agent.py`, `ze_agents/nested_tools.py`, `ze_agents/delegate.py` (+ `test_delegate.py`), `orchestration/nodes/execution.py`, `orchestration/nodes/trace.py`, `telemetry/tracker.py`, their tests (ze-agents `test_script_step.py`, `test_base_agent_loop.py`, `test_nested_tools*.py`; ze-core trace, execution and tracker tests) | T010–T017 | contract step | Gauge |
| stub | Haiku JR | `ze_agents/script_stub.py`, `ze-agents/tests/test_script_stub.py` | T009 | contract step | Gauge |
| sandbox | Sonnet ENG | `sidecar/workspace/**` (`main.py`, `supervisor.py`, `scripts.py`, `script_runtime/`, `Dockerfile`, `requirements.txt`, `tests/`, `README.md`) | T018–T022 | contract step | Gauge |
| runner | Sonnet ENG | `ze_workspace/scripts.py`, `ze_workspace/script_learning.py`, `ze_workspace/client.py`, `ze-workspace/pyproject.toml`, `core/ops/ze-workspace/README.md`, their tests; `procedures/store.py`, `procedures/discovery.py` and their tests | T023–T027 | contract step (T018 frame contract) | Gauge |
| optin | Haiku JR | the four agent files and their tests (attribute only), `ze_eval/scenario.py`, `ze_eval/scoring.py`, ze-eval tests, `eval/scenarios/tool_scripts.yaml` | T028–T030 | T014 merged | Gauge |
| web | Sonnet ENG | `widgets/assemble/ui/trace/ToolsTimeline.tsx` + test, `widgets/assemble/lib/script-rows.ts` + test | T032–T033 | contract step | Gauge |
| docs | Haiku DOCS | `docs/architecture.md`, `docs/configuration.md`, `docs/sdk.md`, `docs/adding-an-agent.md`, `docs/workspace.md`, `docs/eval.md`, `AGENTS.md`, `specs/README.md` | T036 | all lanes merged | Gauge |

**Rules**: one lane per file; shared files belong to `lead` and other lanes request changes; each lane works on a sub-branch of the floor branch and `lead` merges harness → stub → sandbox → runner → optin → web → docs; the sidecar README is the sandbox lane's; the ADR is the lead's; design and cross-layer work stays on Sonnet; the JR lanes get only tasks whose tests are written into the task.

## Complexity Tracking

None.
