# Tasks: Programmatic Tool Use

**Input**: [spec.md](./spec.md) (clarified 2026-10-18), [plan.md](./plan.md) (Lane Plan), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/scripts.md](./contracts/scripts.md), [quickstart.md](./quickstart.md).

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. No real OpenRouter calls; the sidecar is faked in ze-workspace tests and run as a subprocess (no uid switch) in sidecar tests.

**Build gate**: starts after 187b has landed on `main` (`ToolCall.call_id`, `started_at`, the turn recorder). No migration.

## Format: `[ID] [P?] [Lane] [Story] Description`

- **[Lane]**: `[L:lead]`, `[L:harness]`, `[L:stub]`, `[L:sandbox]`, `[L:runner]`, `[L:optin]`, `[L:web]`, `[L:docs]` (plan.md Lane Plan). A task touches only files its lane owns.
- **[Story]**: US1 one script replaces a chain of reads, US2 limits, US3 writes through the gate, US4 trace, US5 procedures.

**Crew**: Sonnet `lead`, `harness`, `sandbox`, `runner`, `web`; Haiku `stub` and `optin` (fully specified) and `docs`. Contract step first; lanes run in parallel in their own worktrees; `lead` merges harness → stub → sandbox → runner → optin → web → docs. Tick a task's checkbox in the same commit that finishes it.

**Rules for every lane**: `graphify affected` and `rtk proxy grep` before changing a shared symbol; typed `ZeError`s; `get_logger(__name__)`; `git add <paths>`, never `-A` or `stash`.

---

## Phase 1: Setup

- [ ] T001 [L:lead] Branch from `main` after 187b landed. `make install`; `graphify update .`; `graphify affected` on `ToolCall`, `ToolCallTrace`, `AgentContext`, `agentic_loop`, `call_tool`, `flatten_tool_calls`, `CostTracker`, `ProcedureMatch`, `ProcedureSourceKind`, `WorkspaceClient`. Confirm `procedure_candidates.source_kind` has no CHECK (zm022) and that versions reach candidates through `admission_id`. Confirm the sidecar image runs as root and `apply_network_isolation` can add a uid rule. Record differences from plan.md "Blast radius" in the Handoffs note and report them to the Spec Architect (Lintel) before T002.

---

## Phase 2: Foundational (contract step, lane `lead`)

- [ ] T002 [L:lead] Tests first `core/contracts/ze-agents/tests/test_scripts_contract.py`: `ScriptLimits()` defaults are 30, 20, 0.05, 4000, 8000; `from_config` reads `workspace.scripts` and falls back per field on a wrong type or a non-positive value; `SCRIPT_TOOL_SCHEMA` names `run_tool_script` with optional `source` and `procedure_id`; `charge_script(0.01)` with no active budget is a no-op, and inside a `ScriptBudget(limit_usd=0.05)` context adds to `spent_usd`, nested tasks share the same budget object; `ScriptError` is a `ZeError` carrying `kind`. Implement `ze_agents/scripts.py` per plan.md "Contract".
- [ ] T003 [L:lead] Tests first: `ToolCall` round-trips `parent_call_id`, `inner_calls` and `script` through the checkpoint serde used for `ParkedLoop` (existing serde test file); `AgentContext.script_runner` defaults to `None` and is excluded from checkpointed state. Add the fields in `ze_agents/types.py` (`BaseAgent.script_tools` is the harness lane's, T012).
- [ ] T004 [L:lead] Tests first: `ToolCallTrace` and `ScriptTrace` JSON round-trip; an old trace without the fields reads with `None`; `ToolCallTraceResponse` and the `trace_update` tool rows carry `parent_call_id` and `script`. Implement in `ze_core/conversation/messages/types.py`, `ze_api/api/v0/messages/schemas.py`, `ze_api/api/ws/schemas.py`, `ze_api/interface/native.py`. Regenerate `@myguyze/ze-client` (`make codegen`).
- [ ] T005 [L:lead] `ProcedureSourceKind.TOOL_SCRIPT = "tool_script"` and `ProcedureMatch.source_kind: str | None = None` in `ze_memory/procedures/types.py`, with a test that a candidate with `TOOL_SCRIPT` round-trips through `ProcedureCandidate` construction.
- [ ] T006 [L:lead] Add the `workspace.scripts` block to `apps/ze-api/config/config.yaml` exactly as in [data-model.md](./data-model.md); `apps/ze-api/tests/test_config_scripts.py` loads the real file (copied to `tmp_path`) and gets the defaults through `ScriptLimits.from_config`.
- [ ] T007 [L:lead] Write the frame contract fixture `core/ops/ze-workspace/tests/fixtures/script_frames.py` (builders for every frame in [contracts/scripts.md](./contracts/scripts.md) plus a scripted fake sidecar that plays a list of frames over an in-memory socket) and add `make test-sidecar` to the `Makefile` (runs `sidecar/workspace/tests` with the workspace venv; `-m "not docker"` by default).
- [ ] T008 [L:lead] `ze_api/wiring/container.py` `_build_config` adds `"script_runner": None` (placeholder until T027 wires the real runner); a test asserts the key is present.

**Checkpoint**: contract merged; lanes start.

---

## Phase 3: User Story 1 - One script replaces a chain of reads (P1) 🎯 MVP

**Goal**: an opted-in agent runs a script whose inner reads go through `call_tool` and returns only the result.

**Independent test**: with a fake runner, the agent's model is called twice in total and the trace holds one script step with its inner calls.

- [ ] T009 [P] [L:stub] [US1] Tests first `core/contracts/ze-agents/tests/test_script_stub.py`, then implement `ze_agents/script_stub.py`:
  - `build_stub([{"type": "function", "function": {"name": "list_goals", "description": "List goals.", "parameters": {"type": "object", "properties": {"status": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["status"]}}}])` contains `def list_goals(*, status: str, limit: int = None):`, the docstring `"""List goals."""`, and `return _call("list_goals", {k: v for k, v in {"status": status, "limit": limit}.items() if v is not None})`;
  - types map `string→str`, `integer→int`, `number→float`, `boolean→bool`, `array→list`, `object→dict`, anything else → no annotation;
  - a tool name that is not a Python identifier (`"bad-name"`) is skipped; a property that is not an identifier is skipped;
  - output is identical for the same schemas in any input order (sorted by name) and always defines `propose` and `finish` and imports `_call`, `ToolError` from `ze_tools_base`;
  - the generated text compiles (`compile(stub, "ze_tools.py", "exec")`);
  - `normalize_source("x = 1  # c\n\n\ny = 'a # b'\n")` == `"x = 1\ny = 'a # b'"`; `source_hash` of two sources differing only in comments and blank lines are equal; differing literals give different hashes.
- [ ] T010 [L:harness] [US1] Tests first `core/contracts/ze-agents/tests/test_script_step.py` with a fake `ScriptRunner` that replays requests: (a) the read set is the visible tools minus server tools, `delegate_to_agent`, `run_tool_script`, `invoke_procedure`, `workspace_*` and WRITE tools; (b) skill narrowing to two read tools gives a stub with exactly those two; (c) a request for a read tool runs `call_tool` with a fresh `call_id`, deps merged and `_`-keys stripped, and replies with JSON data (a non-JSON result arrives as its `_serialise_result` string); (d) a failed inner call replies `ok: false` with the tool error; (e) a request for a tool the agent lacks replies `tool_not_available` and the refusal is a failed inner `ToolCall`; (f) requests are served one at a time in order; (g) `source` over 8,000 chars returns `source_too_long` without calling the runner. Implement `ze_agents/script_step.py` steps 1–5 (plan.md "Loop integration").
- [ ] T011 [L:harness] [US1] Tests first in `core/contracts/ze-agents/tests/test_base_agent_loop.py`: an agent with `script_tools = True`, a runner in `ctx`, and two read tools sees `run_tool_script` in its request and `SCRIPT_GUIDANCE` in its system prompt; without the runner, with `script_tools = False`, or with one read tool it sees neither; a model that calls the tool once and then answers makes exactly two model calls; the script tool message holds only the capped value; `run_tool_script` survives skill narrowing. Implement the loop branch in `ze_agents/base_agent.py`.
- [ ] T012 [L:harness] [US1] `BaseAgent.script_tools: bool = False` in `base_agent.py` with a test; `execute_tool` (`orchestration/nodes/execution.py`) copies `config["configurable"].get("script_runner")` into each `AgentContext` it builds (single and compound paths), and `run_delegate` (`ze_agents/delegate.py`) copies `ctx.script_runner` into `sub_ctx`, so a specialist the conductor delegates to can script too; tests for both (`test_delegate.py`).
- [ ] T013 [L:harness] [US1] Tests first: a script ending `exception`, `bad_request`, `busy` or `unavailable` gives the model the structured error JSON from [contracts/scripts.md](./contracts/scripts.md) with `completed` and `stderr_tail` (last 20 lines), and no partial result as success. Implement in `script_step.py`.

---

## Phase 4: User Story 2 - Limits stop a runaway script (P1)

- [ ] T014 [L:harness] [US2] Tests first in `test_script_step.py`: the 21st request replies `limit: inner_calls` with `stop=True` and the step's `script.limit == "inner_calls"`; with the turn's `ToolCallCapHook` already at 19 calls, the second inner call is aborted by the hook and the script ends; a runner outcome `timeout` sets `limit = "wall_time"`; an inner call whose tool triggers a `CostTracker.record` worth more than the budget makes the next request reply `limit: spend` with `stop=True`; a value over 4,000 chars is cut with `[truncated]` and `limit = "result_size"`. Implement in `script_step.py`.
- [ ] T015 [L:harness] [US2] Tests first `core/engine/ze-core/tests/telemetry/test_tracker_script_budget.py`: `CostTracker.record` inside an active script budget charges the static-price estimate for the model; outside a budget charges nothing; an unknown model charges 0 and logs. Implement in `ze_core/telemetry/tracker.py`.

---

## Phase 5: User Story 3 - Writes in scripts never skip the gate (P2)

- [ ] T016 [L:harness] [US3] Tests first in `test_base_agent_loop.py` and `test_agentic_loop_park.py`: a script finishing with one IRREVERSIBLE and one REVERSIBLE proposed write parks the irreversible one exactly like a direct call (one `ParkedWrite`, `LoopParked` raised, transcript valid with the synthetic call ids) and runs the reversible one with its undo payload; both `ToolCall`s carry `parent_call_id`; in `retry_mode` the irreversible proposal is refused; at the round cap proposals are `refused_over_cap`; a proposal naming a read tool or a tool the agent lacks becomes `not_a_proposable_write`; a forged in-script request for a write tool the agent has replies `writes_must_be_proposed`; resume after approval runs exactly the approved proposal. Implement step 6 and the loop's synthetic-call append.

---

## Phase 6: User Story 4 - The trace shows the script and every call inside it (P2)

- [ ] T017 [L:harness] [US4] Tests first: `flatten_tool_calls` yields the step then its `inner_calls` with `parent_call_id` set (ze-agents nested tools test); `_extract_tool_calls` (`orchestration/nodes/trace.py`, test in `core/engine/ze-core/tests/orchestration/test_message_trace.py`) copies `parent_call_id` and `script` into `ToolCallTrace`, keeps call order, and the 187b call ids match; retry eligibility over a reply with a script step lists a proposed reversible write in the rollback plan and treats inner reads as reads. Implement in `nested_tools.py` and `trace.py`.
- [ ] T032 [P] [L:web] [US4] Tests first `apps/ze-web/src/widgets/assemble/lib/script-rows.test.ts`: `groupScriptRows(rows)` nests rows whose `parent_call_id` matches a script row's `call_id` under it in order, leaves other rows top level, and keeps an orphan (parent missing) top level; `scriptSummary(row)` gives `"Script · ok · 3 calls · 420 ms"` and `"Script · limit: spend · 2 calls · …"`. Implement `widgets/assemble/lib/script-rows.ts`.
- [ ] T033 [L:web] [US4] Tests first `ToolsTimeline.test.tsx`: a script row draws its summary collapsed, and expanded shows the source in a monospace scrollable block (with a "cut" note when `source_cut`) and its child rows; keyboard toggles it (Enter/Space, `aria-expanded`). Implement in `widgets/assemble/ui/trace/ToolsTimeline.tsx`. `make test-web` and `make typecheck-web` pass.

---

## Phase 7: The sandbox and the runner (US1, US2)

- [ ] T018 [P] [L:sandbox] [US1] Tests first `sidecar/workspace/tests/test_scripts_relay.py` (subprocess as the current user; uid switch skipped when not root): `WS /scripts` rejects a missing or wrong token before accept; `start` writes `ze_tools.py` (`script_runtime/ze_tools_base.py` + stub) and `main.py` into a fresh scratch dir and runs it; a script calling `z.echo(x=1)` produces a `call` frame and continues with the `reply` value; `finish(v, writes=[...])` ends with `status: ok`, `value`, `writes`; an uncaught exception ends `exception` with the exception line and the last 20 stderr lines; the scratch dir is gone after `end`. Implement `sidecar/workspace/scripts.py`, `script_runtime/`, and the route in `main.py`; add `websockets` to `requirements.txt` only if the test client needs it.
- [ ] T019 [L:sandbox] [US2] Tests first: `timeout_seconds: 1` with `while True: pass` ends `timeout` and the process group is gone; `cancel` ends `killed`; a malformed request line ends `bad_request`; more than `2 × 20` request lines end `bad_request`; a second connection during a run gets `end` with `busy`; a workspace run (`POST /run`) proceeds while a script runs (separate slot). Implement the `ScriptSlot`.
- [ ] T020 [L:sandbox] [US1] `Dockerfile`: add system user `zescript` (home `/tmp/ze-scripts`), `chmod 0750 /workspace`, copy `scripts.py` and `script_runtime/`; spawn scripts as `zescript` with `python3 -I -X utf8`, env limited to `PATH`, `HOME`, `LANG`, `ZE_REQ_FD`, `ZE_REP_FD`. Test (unit): `script_env()` returns exactly those keys.
- [ ] T021 [L:sandbox] [US1] `apply_network_isolation` adds a rule dropping all output from `zescript`'s uid (nft `meta skuid`, iptables `--uid-owner` fallback) and records whether it applied; `/stat` gains `scripts_busy` and `scripts_isolated`. Unit test with the command runner faked; `sidecar/workspace/tests/smoke_scripts.py` (marked `docker`) checks no network and no `/workspace` access as in [quickstart.md](./quickstart.md).
- [ ] T022 [L:sandbox] Update `sidecar/workspace/README.md`: `WS /scripts`, frames, the `zescript` user, the script slot, `scripts_isolated`, the smoke test.
- [ ] T023 [P] [L:runner] [US1] Tests first `core/ops/ze-workspace/tests/test_script_runner.py` with the T007 fake sidecar: `WorkspaceScriptRunner.run` sends `start` with the token, relays each `call` to `dispatch` and sends its `reply`; a `DispatchReply(stop=True)` sends `cancel` after the reply; `end` maps to `ScriptOutcome`; connection refused → `unavailable`; `end busy` → `busy`; no `end` within `wall_seconds + 5` → cancel and `timeout`; `/stat` with `scripts_isolated: false` → `unavailable` without opening the socket. Implement `ze_workspace/scripts.py`, `WorkspaceClient.scripts_url()` and `stat` parsing of the new fields in `client.py`; add `websockets==16.0` to `core/ops/ze-workspace/pyproject.toml`.

---

## Phase 8: User Story 5 - A script that keeps working becomes a procedure (P3)

- [ ] T024 [L:runner] [US5] Tests first `core/ops/ze-workspace/tests/test_script_learning.py` (mock stores): every finished script appends one action record (`source_record_type = "tool_script"`, `source_record_id = source_hash`, outcome succeeded/failed, actor = agent); the third consecutive success by one agent submits exactly one candidate shaped as in [data-model.md](./data-model.md); a fourth success submits nothing (`candidate_exists` true); a failure between successes resets the run; successes by two agents do not combine; a run with `procedure_id` never submits; a store error is logged and never raised. Implement `ze_workspace/script_learning.py`; the runner calls it fire-and-forget after each run.
- [ ] T025 [L:runner] [US5] Tests first: `procedures/store.py` returns `source_kind` for a version through `admission_id → candidate_id` (NULL when no admission) and `candidate_exists(name)`; add one `@pytest.mark.pg` test for the join. `discovery.py` fills `ProcedureMatch.source_kind`. Implement.
- [ ] T026 [L:harness] [US5] Tests first in `test_script_step.py`: `procedure_id` of a READY match with `source_kind == "tool_script"` runs `steps[0]` with a stub built from the agent's current tools (a tool listed in the procedure's limits that the agent no longer has is absent from the stub); a non-script or non-READY match returns `procedure_not_script`. Implement in `script_step.py`.
- [ ] T027 [L:runner] [US1] Construct `WorkspaceScriptRunner` (with `ScriptLearning`) in the ze-workspace bootstrap and expose it for wiring; hand `lead` the one-line change for `_build_config` (lead applies it in T031). Test: bootstrap returns a runner when the sidecar is configured, `None` otherwise.

---

## Phase 9: Opt-in and eval

- [ ] T028 [P] [L:optin] Set `script_tools = True` on `plugins/ze-personal/ze_personal/agents/companion/agent.py`, `plugins/ze-calendar/ze_calendar/agents/calendar/agent.py`, `plugins/ze-messenger/ze_messenger/agents/messenger/agent.py`, `plugins/ze-finance/ze_finance/agents/finance/agent.py`; add one assertion per agent's existing test file (`assert CompanionAgent.script_tools is True`, and so on) and one in a core agent test that `ResearchAgent.script_tools is False`.
- [ ] T029 [L:optin] Tests first `core/ops/ze-eval/tests/test_scoring.py`: a scenario with `max_llm_calls: 3` fails when the run's `llm_calls` is 4 and passes at 3; a scenario without the field ignores the count. Implement the field in `ze_eval/scenario.py` and the check in `ze_eval/scoring.py`.
- [ ] T030 [L:optin] Write `eval/scenarios/tool_scripts.yaml` with the two scenarios in plan.md "Eval" (tag `tool_scripts`, `expected_tools: [run_tool_script]`, `max_llm_calls: 3`, criteria on the answer). `make test-eval` passes (the loader parses it). No live run without the user's OK.

---

## Phase 10: Polish and cross-cutting

- [ ] T031 [L:lead] Wire the real runner: `_build_config` sets `script_runner` from the ze-workspace bootstrap (T027); integration test with a fake runner: a companion turn that scripts two reads ends with a trace holding the step and both inner calls.
- [ ] T034 [L:lead] Write the ADR `specs/arch/programmatic-tool-use.md` (plan.md "Docs"), following the existing ADR format.
- [ ] T036 [L:docs] Docs per plan.md "Docs": `docs/architecture.md` (script path; diagram if it helps, per the diagram rule), `docs/configuration.md` (`workspace.scripts`), `docs/sdk.md`, `docs/adding-an-agent.md`, `docs/workspace.md`, `docs/eval.md`, `AGENTS.md` (layout lines, phase row 197, Learned Workspace Fact), `specs/README.md` row. Follow the `doc-style` skill. Coverage check: every public doc in `git diff main...HEAD --stat` and every doc naming `workspace_run`, `invoke_procedure` or the eval scenario fields is updated or recorded as needing no change in the Handoffs note.
- [ ] T035 [L:lead] Merge lanes; run `make lint`, `make test-py`, `make test-sidecar`, `make test-web`, `make typecheck-web`; with Docker, the quickstart smoke test. With the user's OK only: `python eval/run.py --tag tool_scripts`, record `llm_calls` against the direct-call baseline (same prompts with `script_tools` off) for SC-001. Record results in the Handoffs note; mark the spec Implemented and set floor status review.

---

## Dependencies & Execution Order

- 187b on `main` → T001 → T002–T008 (contract) → lanes in parallel.
- `harness`: T010 → T011 → T012 → T013 → T014 → T015 → T016 → T017 → T026 (T010 needs T009's stub builder: until `stub` merges, T010 uses a stub fake).
- `stub`: T009. `sandbox`: T018 → T019 → T020 → T021 → T022. `runner`: T023 → T024 → T025 → T027 (T023 needs T007's fixture).
- `optin`: T028 after T011 merged; T029 → T030. `web`: T032 → T033.
- `lead`: T031 after harness, runner merged; T034 any time after the contract; `docs` after all lanes; T035 last.

## Parallel Example

After the contract step: `harness` T010, `stub` T009, `sandbox` T018, `runner` T023, `web` T032 and `optin` T029 start together.

## Implementation Strategy

MVP = contract + US1 + US2 (reads with limits, sandbox, runner). US3 writes, US4 trace UI, US5 learning, eval and docs complete the phase.

## Handoffs

Lane leads record blast-radius differences, gate runs, the smoke test and doc coverage in the build floor's Handoffs note.
