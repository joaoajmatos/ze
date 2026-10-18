# Tasks: Programmatic Tool Use

**Input**: [spec.md](./spec.md) (clarified 2026-10-18, revised after Gauge review), [plan.md](./plan.md) (Lane Plan), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/scripts.md](./contracts/scripts.md), [quickstart.md](./quickstart.md).

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. No real OpenRouter calls; the sidecar is faked in ze-workspace tests and run as a subprocess (no uid switch) in sidecar tests; uid, rlimit and nft checks run in the Docker smoke test.

**Build gate**: starts after 187b has landed on `main` (`ToolCall.call_id`, `started_at`, the turn recorder). No migration.

## Format: `[ID] [P?] [Lane] [Story] Description`

- **[Lane]**: `[L:lead]`, `[L:harness]`, `[L:stub]`, `[L:sandbox]`, `[L:runner]`, `[L:flags]`, `[L:web]`, `[L:docs]` (plan.md Lane Plan). A task touches only files its lane owns.
- **[Story]**: US1 one script replaces a chain of reads, US2 limits, US3 writes through the gate, US4 trace, US5 procedures.

**Crew**: Sonnet `lead`, `harness`, `sandbox`, `runner`, `web`; Haiku `stub` and `flags` (fully specified) and `docs`. Contract step first; lanes run in parallel in their own worktrees; `lead` merges harness → stub → sandbox → runner → flags → web → docs. Tick a task's checkbox in the same commit that finishes it.

**Rules for every lane**: `graphify affected` and `rtk proxy grep` before changing a shared symbol; typed `ZeError`s; `get_logger(__name__)`; `git add <paths>`, never `-A` or `stash`.

---

## Phase 1: Setup

- [x] T001 [L:lead] Branch from `main` after 187b landed. `make install`; `graphify update .`; `graphify affected` on `ToolCall`, `ToolCallTrace`, `AgentContext`, `ActionContext`, `agentic_loop`, `call_tool`, `flatten_tool_calls`, `ToolCallCapHook`, `retry_eligibility`, `CostTracker`, `ProcedureMatch`, `format_procedure_guidance`, `WorkspaceStack`. List, per registered agent, whether it has a data read tool once `produces_ui` is set on render and show tools (expected: companion none), and every READ tool that takes a caller-chosen URL or host (expected: `browser_extract`), for `egress`. Confirm `procedure_candidates.source_kind` has no CHECK and that versions reach candidates through `admission_id`; confirm the sidecar runs as root, `/workspace` is a volume mount in `fly.toml` and `docker-compose.yml`, and `apply_network_isolation` can add a uid rule. Record differences from plan.md "Blast radius" in the Handoffs note and report them to the Spec Architect (Lintel) before T002.

---

## Phase 2: Foundational (contract step, lane `lead`)

- [x] T002 [L:lead] Tests first `core/contracts/ze-agents/tests/test_scripts_contract.py`: `ScriptLimits()` defaults (30, 20, 10, 0.05, 4000, 8000; byte caps 262144 and 1048576; stored inner result 2000); `from_config` reads `workspace.scripts` and falls back per field on a wrong type or a non-positive value; `SCRIPT_TOOL_SCHEMA` names `run_tool_script` with optional `source` and `procedure_id`; `charge_script(0.01)` with no active budget is a no-op and inside a budget adds to `spent_usd` (nested tasks share the budget object); `in_script_call` defaults to false; `ScriptError` is a `ZeError` with `kind`. Then `@tool(produces_ui=True)` and `@tool(egress=True)` set `ToolSpec.produces_ui` and `ToolSpec.egress`, both false by default (`test_tool.py` or a sibling). Implement `ze_agents/scripts.py` and the two flags in `ze_agents/tool.py`.
- [x] T003 [L:lead] Tests first: `ToolCall` round-trips `parent_call_id`, `inner_calls` and `script` through the checkpoint serde used for `ParkedLoop`; `AgentContext.script_runner` defaults to `None` and is not checkpointed; `ActionContext(script_key="k")` serializes into the `context` JSON and back. Add the fields in `ze_agents/types.py` and `ze_memory/action_records/types.py`.
- [x] T004 [L:lead] Tests first: `ToolCallTrace` and `ScriptTrace` JSON round-trip; an old trace without the fields reads with `None`; `access` accepts `"script"`; `ToolCallTraceResponse` (access union includes `"script"`) and the `trace_update` tool rows carry `parent_call_id` and `script`. Implement in `ze_core/conversation/messages/types.py`, `ze_api/api/v0/messages/schemas.py`, `ze_api/api/ws/schemas.py`, `ze_api/interface/native.py`. Regenerate `@myguyze/ze-client` (`make codegen`).
- [x] T005 [L:lead] `ProcedureSourceKind.TOOL_SCRIPT = "tool_script"` and `ProcedureMatch.source_kind: str | None = None` in `ze_memory/procedures/types.py`, with a test that a `TOOL_SCRIPT` candidate with `preconditions=[]` constructs.
- [x] T006 [L:lead] Add the `workspace.scripts` block to `apps/ze-api/config/config.yaml` exactly as in [data-model.md](./data-model.md); `apps/ze-api/tests/test_config_scripts.py` loads the real file (copied to `tmp_path`) and gets the defaults through `ScriptLimits.from_config`.
- [x] T007 [L:lead] Write the frame contract fixture `core/ops/ze-workspace/tests/fixtures/script_frames.py`: builders for every frame in [contracts/scripts.md](./contracts/scripts.md) plus a scripted fake sidecar that plays a list of frames over an in-memory socket and records what Ze sent.
- [x] T008 [L:lead] `ze_api/wiring/container.py` `_build_config` adds `"script_runner": None` (placeholder until T031); a test asserts the key is present.

**Checkpoint**: contract merged; lanes start.

---

## Phase 3: User Story 1 - One script replaces a chain of reads (P1) 🎯 MVP

**Goal**: any agent with a data read tool runs a script whose inner reads go through `call_tool` and returns only the result.

**Independent test**: with a fake runner, the agent's model is called twice in total and the trace holds one script step with its inner calls.

- [ ] T009 [P] [L:stub] [US1] Tests first `core/contracts/ze-agents/tests/test_script_stub.py`, then implement `ze_agents/script_stub.py`:
  - `build_stub([{"type": "function", "function": {"name": "get_transactions", "description": "List transactions.", "parameters": {"type": "object", "properties": {"period": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["period"]}}}])` contains `def get_transactions(*, period: str, limit: int = None):`, the docstring `"""List transactions."""`, and `return _call("get_transactions", {k: v for k, v in {"period": period, "limit": limit}.items() if v is not None})`;
  - types map `string→str`, `integer→int`, `number→float`, `boolean→bool`, `array→list`, `object→dict`, anything else → no annotation;
  - a tool name or property that is not a Python identifier (`"bad-name"`) is skipped;
  - output is identical for the same schemas in any input order (sorted by name), always defines `propose` and `finish`, and imports `_call` and `ToolError` from `ze_tools_base`; the text compiles (`compile(stub, "ze_tools.py", "exec")`);
  - `normalize_source("x = 1  # c\n\n\ny = 'a # b'\n") == "x = 1\ny = 'a # b'"`; `source_hash` ignores comments and blank lines and changes with literals;
  - `tool_signature("finance", ["get_transactions", "get_positions", "get_transactions"])` equals `tool_signature("finance", ["get_transactions", "get_positions"])` and differs from the same names in the other order or for another agent.
- [ ] T010 [L:harness] [US1] Tests first `core/contracts/ze-agents/tests/test_script_step.py` with a fake `ScriptRunner` that replays requests:
  - (a) the data-read set is the visible tools minus server tools, `delegate_to_agent`, `run_tool_script`, `invoke_procedure`, `workspace_*`, WRITE tools, `produces_ui` tools and `egress` tools (a fake `render_chart`, a fake `show_topic` and a fake `browser_extract` are excluded);
  - (b) skill narrowing to two read tools gives a stub with exactly those two;
  - (c) a request for a read tool runs `call_tool` with a fresh `call_id`, deps merged and `_`-keys stripped;
  - (d) reply encoding: a tool returning `'{"a": 1}'` replies `{"a": 1}`; a dict holding a `datetime`, a `UUID` and a `Decimal` replies with ISO and string values and stays a dict; plain text stays a string; a value over 1 MiB replies `ok: false, error: "result_too_large"`;
  - (e) the stored inner `ToolCall.result` is cut to 2,000 chars while the reply carries the full value;
  - (f) a failed inner call replies `ok: false` with the tool error;
  - (g) a request for a tool the agent lacks replies `tool_not_available`, for a write tool the agent has `writes_must_be_proposed`, and for a malformed request (`tool` not a string, `args` not a dict) `bad_request`; each refusal is a failed inner `ToolCall`;
  - (h) requests are served one at a time in order;
  - (i) `source` over 8,000 chars returns `source_too_long` without calling the runner.

  Implement `ze_agents/script_step.py` steps 1–5 (plan.md "Loop integration").
- [ ] T011 [L:harness] [US1] Tests first in `core/contracts/ze-agents/tests/test_base_agent_loop.py`: an agent with a runner in `ctx` and one data read tool sees `run_tool_script` in its request and `SCRIPT_GUIDANCE` in its system prompt; with no runner, or with only UI and write tools (a companion-like tool list), it sees neither; a model that calls the tool once and then answers makes exactly two model calls; the script tool message holds only the capped value; `run_tool_script` survives skill narrowing and procedure narrowing (`procedure_tool_names` set). Implement in `ze_agents/base_agent.py` (`names` addition, schema substitution, guidance appended once before the loop, the narrowing rule beside `invoke_procedure`).
- [ ] T012 [L:harness] [US1] `execute_tool` (`orchestration/nodes/execution.py`) copies `config["configurable"].get("script_runner")` into each `AgentContext` it builds (single and compound paths), and `run_delegate` (`ze_agents/delegate.py`) copies `ctx.script_runner` into `sub_ctx`; tests for both (`test_delegate.py`).
- [ ] T013 [L:harness] [US1] Tests first: a script ending `exception`, `bad_request`, `busy`, `unavailable` or `resource_limit` gives the model the structured error JSON from [contracts/scripts.md](./contracts/scripts.md) with `completed`, `stderr_tail` (last 20 lines) and, on `exception`, `last_result_shape` built from the last successful inner result (a list of dicts gives `list[dict] keys: ...`, at most 20 keys); no partial result is shown as success. Implement in `script_step.py`.

---

## Phase 4: User Story 2 - Limits stop a runaway script (P1)

- [ ] T014 [L:harness] [US2] Tests first in `test_script_step.py` and `core/contracts/ze-agents/tests/test_tool_cap_hook*.py`: the 21st request replies `limit: inner_calls` with `stop=True` and `script.limit == "inner_calls"`; `ToolCallCapHook` does not count calls made while `in_script_call` is set; a script of 20 inner reads followed by one proposed write with the turn cap at 20 still reaches the write gate (the write is counted, the reads are not); a runner outcome `timeout` sets `limit = "wall_time"`; an inner call whose tool triggers a `CostTracker.record` worth more than the budget makes the next request reply `limit: spend` (the overshooting call itself completes); a value over 4,000 chars is cut with `[truncated]` and `limit = "result_size"`. Implement in `script_step.py` and `ze_agents/tool_cap_hook.py`.
- [ ] T015 [L:harness] [US2] Tests first `core/engine/ze-core/tests/telemetry/test_tracker_script_budget.py`: `CostTracker.record` inside an active script budget charges the static-price estimate for the model; outside a budget charges nothing; an unknown model charges the table's default price. Implement in `ze_core/telemetry/tracker.py`.

---

## Phase 5: User Story 3 - Writes in scripts never skip the gate (P2)

- [ ] T016 [L:harness] [US3] Tests first in `test_base_agent_loop.py` and `test_agentic_loop_park.py`:
  - a script finishing with one IRREVERSIBLE and one REVERSIBLE proposed write parks the irreversible one exactly like a direct call (one `ParkedWrite`, `LoopParked` raised) and runs the reversible one with its undo payload; both `ToolCall`s carry `parent_call_id`;
  - the synthetic ids are `<model id>_w0`, `<model id>_w1`, match `^[A-Za-z0-9_-]{1,64}$` (a model id with `:` or 70 chars is sanitized and cut), and appear in `messages[-1]["tool_calls"]` before `LoopParked` is raised, so the checkpointed `ParkedLoop.messages` holds them and resume after approval runs exactly the approved proposal (`_apply_resume` finds it by `call_id`);
  - in `retry_mode` the irreversible proposal is refused; at the round cap proposals are `refused_over_cap`;
  - a proposal naming a read tool or a tool the agent lacks, a malformed proposal, and the 11th proposal become `not_a_proposable_write`.

  Implement step 6 and the loop's synthetic-call append.

---

## Phase 6: User Story 4 - The trace shows the script and every call inside it (P2)

- [ ] T017 [L:harness] [US4] Tests first:
  - `flatten_tool_calls` (ze-agents nested tools test) is depth-first: [delegate call, script step (2 inner), other call] flattens to delegate, step, inner 1, inner 2, other; inner calls get `parent_call_id`; a script step whose result JSON holds a `tool_calls` key, and an inner call whose result does, produce no extra rows;
  - `_extract_tool_calls` (`core/engine/ze-core/tests/orchestration/test_message_trace.py`) gives the step `access == "script"`, copies `parent_call_id` and `script`, keeps the flattened order, and the 187b call ids match;
  - `retry_eligibility` (ze-core retry test) accepts a reply with a script step and inner reads (not `unknown_tool`), and lists a proposed reversible write in the rollback plan.

  Implement in `nested_tools.py`, `trace.py` and `conversation/retry.py`.
- [ ] T032 [P] [L:web] [US4] Tests first `apps/ze-web/src/widgets/assemble/lib/script-rows.test.ts`: `groupScriptRows(rows)` nests rows whose `parent_call_id` matches a script row's `call_id` under it in order, leaves other rows top level, and keeps an orphan top level; `scriptSummary(row)` gives `"Script · ok · 3 calls · 420 ms"` and `"Script · limit: spend · 2 calls · …"`; `access: "script"` styles like `delegate`. Implement `widgets/assemble/lib/script-rows.ts`.
- [ ] T033 [L:web] [US4] Tests first in the existing `widgets/assemble/ui/trace/instruments.test.tsx`: a script row draws its summary collapsed; expanded it shows the source in a monospace scrollable block (with a "cut" note when `source_cut`) and its child rows; Enter/Space toggle it with `aria-expanded`. Implement in `widgets/assemble/ui/trace/ToolsTimeline.tsx`. `make test-web` and `make typecheck-web` pass.

---

## Phase 7: The sandbox and the runner (US1, US2)

- [ ] T018 [P] [L:sandbox] [US1] Tests first `sidecar/workspace/tests/test_scripts_relay.py` (subprocess as the current user; uid switch skipped when not root):
  - `WS /scripts` with a missing or wrong token, and with `WORKSPACE_API_TOKEN` empty, fails the handshake with close code 1008 (`WebSocketException`, raised before accept);
  - `start` writes `ze_tools.py`, `main.py` and `_ze_main.py` into a fresh scratch dir and spawns `python3 -I -X utf8 _ze_main.py`; `import ze_tools` works through the real spawn;
  - a script calling `z.echo(x=1)` produces a `call` frame and continues with the `reply` value;
  - `finish(v, writes=[...])` ends `ok` with `value` and `writes`; a `writes` entry without `tool` or `args` ends `bad_request`;
  - an uncaught exception ends `exception` with the exception line and the last 20 stderr lines;
  - `print("x" * 10_000_000)` does not block (stdout is DEVNULL);
  - the scratch dir is gone after `end`.

  Implement `sidecar/workspace/scripts.py`, `script_runtime/`, and the route in `main.py`; add `websockets` to `requirements.txt` only if the test client needs it.
- [ ] T019 [L:sandbox] [US2] Tests first:
  - `timeout_seconds: 1` with `while True: pass` ends `timeout`, and no process of the script user remains (a child started with `os.setsid()` is killed too; tested by pid when not root);
  - `cancel` ends `killed`;
  - a request line over 256 KB, a `finish` line over 1 MiB, malformed JSON, and more than `2 × 20` request lines each end `bad_request`;
  - a script writing two 15 MiB files then sleeping is killed `resource_limit` before its wall time (the scratch size is polled during the run); a scratch dir over 32 MiB at end also ends `resource_limit`;
  - a second connection during a run gets `end` with `busy`;
  - a workspace run (`POST /run`) proceeds while a script runs (separate slot);
  - the WS `max_size` is 2 MiB.

  Implement the `ScriptSlot`, the caps and the uid-wide kill.
- [ ] T020 [L:sandbox] [US1] `Dockerfile`: add system user `zescript` (home `/tmp/ze-scripts`), copy `scripts.py` and `script_runtime/`. Spawn scripts as `zescript` with rlimits in the preexec: `RLIMIT_AS` 256 MiB, `RLIMIT_NPROC` 32, `RLIMIT_FSIZE` 16 MiB, `RLIMIT_CPU` wall + 1 s, `RLIMIT_NOFILE` 64. Env limited to `PATH`, `HOME`, `LANG`, `ZE_REQ_FD`, `ZE_REP_FD`. Unit tests: `script_env()` returns exactly those keys; `script_rlimits(limits)` returns those five values; an exit by SIGKILL/SIGXCPU/SIGXFSZ or a `MemoryError` stderr maps to `resource_limit`.
- [ ] T021 [L:sandbox] [US1] Isolation:
  - the lifespan sets `/workspace` to mode 0750 at runtime, after `apply_network_isolation`;
  - `apply_network_isolation` adds a `reject` rule for all output from `zescript`'s uid (nft `meta skuid`, iptables `--uid-owner` fallback) and verifies it by listing the chain and finding the rule;
  - `/stat` gains `scripts_busy` and `scripts_isolated` (rule verified and mode set);
  - `_ze_main.py` runs the per-script probe (cannot list `/workspace`, a TCP connect to `1.1.1.1:53` with a 0.5 s timeout fails) and on a breach writes `isolation_breach`; the sidecar then ends the script `unavailable` and sets `scripts_isolated` false;
  - `docker-compose.yml`: `cap_add: [NET_ADMIN]` on the workspace service.

  Unit tests with the command runner faked: verification reads the chain listing (a successful command whose listing lacks the rule gives `scripts_isolated` false); probe breach handling. `sidecar/workspace/tests/smoke_scripts.py` (marked `docker`) covers every check in [quickstart.md](./quickstart.md).
- [ ] T022 [L:sandbox] Update `sidecar/workspace/README.md`: `WS /scripts`, frames and caps, the `zescript` user, rlimits, stdout discarded, the script slot, `scripts_isolated` and the probe, `cap_add: [NET_ADMIN]` for local dev, the smoke test.
- [x] T023 [P] [L:runner] [US1] Tests first `core/ops/ze-workspace/tests/test_script_runner.py` with the T007 fake sidecar: `WorkspaceScriptRunner.run` sends `start` with the token; relays each `call` to `dispatch` and sends its `reply`; a `DispatchReply(stop=True)` sends `cancel` after the reply; `end` maps to `ScriptOutcome` (all eight statuses); connection refused → `unavailable`; `end busy` → `busy`; no `end` within `wall_seconds + 5` → cancel and `timeout`; `/stat` with `scripts_isolated: false` → `unavailable` without opening the socket; the client's `max_size` is 2 MiB. Implement `ze_workspace/scripts.py`, `WorkspaceClient.scripts_url()` and the new `stat` fields in `client.py`; add `websockets==16.0` to `core/ops/ze-workspace/pyproject.toml`.

---

## Phase 8: User Story 5 - A script that keeps working becomes a procedure (P3)

- [x] T024 [L:runner] [US5] Tests first:
  - `core/ops/ze-workspace/tests/test_script_learning.py`, running the real `ActionRecorder` over a fake store that enforces the real idempotency key: every finished script appends its own record (three runs of one tool signature give three rows); fields per [data-model.md](./data-model.md) (lifecycle and outcome values, `failure_code`, `ActionContext.script_key`, which round-trips through `_context_to_json` and the row reader in `action_records/store.py`); the third consecutive success for a key submits exactly one candidate (name `Script: <tools in order> [<key prefix>]` within 120 chars, latest source as its step, `preconditions=[]`, the three record ids as evidence); a fourth success submits nothing (`candidate_exists` true); a failure between successes resets the run; two agents with the same tools do not combine; a run with `procedure_id` never submits; a store error is logged and never raised;
  - one `@pytest.mark.pg` test: three runs of one key leave three `action_records` rows, and `list_by_script_key` returns them newest first.

  Implement `ze_workspace/script_learning.py` (copying `ze_workspace/action_records.py`'s pattern) and `ActionRecordStore.list_by_script_key` in `ze_memory/action_records/store.py`; the runner calls learning fire-and-forget after each run.
- [x] T025 [L:runner] [US5] Tests first:
  - `procedures/store.py`: `list_active_versions` returns `source_kind` per version through one LEFT JOIN (`admission_id → candidate_id`, NULL without an admission), with no extra query per version; `candidate_exists(name)`; one `@pytest.mark.pg` test for the join;
  - `discovery.py` fills `ProcedureMatch.source_kind`, and `format_procedure_guidance` prints a `tool_script` match as one line pointing to `run_tool_script(procedure_id="<id>")` with no steps;
  - `validate_candidate` rejects a `tool_script` candidate without `evidence_refs`, with two steps, or with a step over 8,000 chars;
  - `invoke_procedure` on a script procedure records the invocation and returns the run-it-with-`run_tool_script` text.

  Implement in `procedures/store.py`, `discovery.py`, `validate.py`, `tools.py`.
- [ ] T026 [L:harness] [US5] Tests first in `test_script_step.py`: `procedure_id` of a READY match with `source_kind == "tool_script"` runs `steps[0]` with a stub built from the agent's current data read tools (a tool in the procedure's limits that the agent no longer has is absent from the stub); a non-script or non-READY match returns `procedure_not_script`. Implement in `script_step.py`.
- [ ] T027 [L:runner] [US1] `WorkspaceStack.script_runner` and `build_workspace_stack(procedure_admission=...)` in `ze_workspace/bootstrap.py`: builds `WorkspaceScriptRunner` (with `ScriptLearning` when the action store and admission service are given) when the sidecar is configured. Test: a runner when configured, `None` otherwise, learning absent without the admission service.

---

## Phase 9: UI flag and eval

- [ ] T028 [P] [L:flags] Tests first: every tool registered by `ze_components.tools.render_tool` has `produces_ui is True` (`core/kernel/ze-components/tests/`), and `show_slipping`, `show_decisions`, `show_topic` have it (`core/arbitration/ze-priority/tests/`); a plain READ tool does not; `browser_extract` has `egress is True` (`integrations/ze-browser/tests/`); `apps/ze-api/tests/test_tool_egress_flags.py` loads every plugin's agent modules (the `agent_module_paths()` loop of `test_tool_reversibility.py`) and fails when a READ tool has a parameter named `url`, `uri`, `link`, `host`, `endpoint` or `domain` without `egress` or an entry in an exemption dict with a reason. Implement: `render_tool` passes `produces_ui=True` to the `ToolSpec` it builds; the three `@tool(...)` declarations in `ze_priority/compose/tools.py` add `produces_ui=True`; `browser_extract` adds `egress=True` (plus any tool T001 listed).
- [ ] T029 [L:flags] Tests first `core/ops/ze-eval/tests/test_scoring.py`: a scenario with `max_llm_calls: 3` fails when the run's `llm_calls` is 4 and passes at 3; a scenario without the field ignores the count. Implement the field in `ze_eval/scenario.py` and the check in `ze_eval/scoring.py`.
- [ ] T030 [L:flags] Write `eval/scenarios/tool_scripts.yaml` with the three scenarios in plan.md "Eval" (finance, messenger, calendar; tag `tool_scripts`, `expected_tools: [run_tool_script]`, `max_llm_calls: 3`, criteria on the answer). `make test-eval` passes (the loader parses it). No live run without the user's OK.

---

## Phase 10: Polish and cross-cutting

- [ ] T031 [L:lead] Wire the real runner: `_build_config` sets `script_runner` from `WorkspaceStack.script_runner`, and the container passes the procedure admission service to `build_workspace_stack`. Integration test with a fake runner: a finance turn that scripts two reads ends with a trace holding the step (`access: script`) and both inner calls, and a companion turn has no script tool.
- [x] T034 [L:lead] Write the ADR `specs/arch/programmatic-tool-use.md` (plan.md "Docs"), following the existing ADR format.
- [ ] T036 [L:docs] Docs per plan.md "Docs": `docs/architecture.md` (script path; diagram if it helps, per the diagram rule), `docs/configuration.md` (`workspace.scripts`), `docs/sdk.md`, `docs/adding-an-agent.md`, `docs/workspace.md` (limits, `cap_add`, unavailable without it), `docs/eval.md`, `AGENTS.md` (layout lines, phase row 197, Learned Workspace Fact), `specs/README.md` row. Follow the `doc-style` skill. Coverage check: every public doc in `git diff main...HEAD --stat`, and every doc naming `workspace_run`, `invoke_procedure`, `render_tool` or the eval scenario fields, is updated or recorded as needing no change in the Handoffs note.
- [ ] T035 [L:lead] Merge lanes; run `make lint`, `make test-py`, `make test-workspace-sidecar`, `make test-pg`, `make test-web`, `make typecheck-web`; with Docker, the quickstart smoke test. With the user's OK only: `python eval/run.py --tag tool_scripts`, recording `llm_calls` against the direct-call baseline (same prompts with no runner wired) for SC-001, and re-run the existing routing scenarios and each scenario file of an agent that now carries the script schema, since every such request grows by the schema and `SCRIPT_GUIDANCE`; without the OK, record them as not run in the Handoffs note. Record results in the Handoffs note; mark the spec Implemented and set floor status review.

---

## Dependencies & Execution Order

- 187b on `main` → T001 → T002–T008 (contract) → lanes in parallel.
- `harness`: T010 → T011 → T012 → T013 → T014 → T015 → T016 → T017 → T026 (until `stub` merges, T010 uses a stub fake).
- `stub`: T009. `sandbox`: T018 → T019 → T020 → T021 → T022. `runner`: T023 → T024 → T025 → T027 (T023 needs T007's fixture).
- `flags`: T028 ∥ T029 → T030. `web`: T032 → T033.
- `lead`: T031 after harness, runner and flags merged; T034 any time after the contract; `docs` after all lanes; T035 last.

## Parallel Example

After the contract step: `harness` T010, `stub` T009, `sandbox` T018, `runner` T023, `web` T032 and `flags` T028/T029 start together.

## Implementation Strategy

MVP = contract + US1 + US2 (reads with limits, sandbox, runner). US3 writes, US4 trace UI, US5 learning, eval and docs complete the phase.

## Handoffs

Lane leads record blast-radius differences, gate runs, the smoke test and doc coverage in the build floor's Handoffs note.
