# Feature Specification: Programmatic Tool Use

**Feature Branch**: `197-programmatic-tool-use`

**Created**: 2026-10-18

**Status**: Implemented (Gauge APPROVE 2026-10-21; Docker sandbox smoke 11/11; live evals not run, see the phase Handoffs)

**Input**: User description (approved 2026-10-18, "yes do all of that"): models write short scripts that call several tools, loop and compute, and return only the result to the model, for fewer round trips, fewer tokens and more autonomy. Scripts run in the phase 115 workspace sandbox, never a hosted third-party sandbox. Ze's tools are exposed inside the sandbox as a small typed Python API, filtered to the calling agent's own tools and skill narrowing. Read tools first; writes inside scripts go through the 181 write gate (same or later phase, decided here). Every inner call is a tool call on the trace with 187b telemetry; the script is one traced step with its source stored. Limits: wall time, inner calls, cost per script; failure returns a structured error. A script that keeps succeeding can become a procedure candidate (138/139). Eval scenarios show fewer model round trips on multi-step reads; no live calibration spend without the user's OK.

**Governed by**: `PRODUCT.md` principle 4 (unattended work is accountable), phase 115/116/129 (workspace sidecar, follow-through, run journal), phase 114 (skill narrowing), phase 181 (irreversible writes ask first), phase 180 (undo payloads), phase 187b (trace telemetry: `call_id`, offsets, durations), phases 138/139 (procedure lifecycle and activation), phase 22 (tool-call cap), `specs/arch/pre-v1-hard-cuts.md`. The decision record in `research.md` records the channel and trust decisions.

**Depends on**: 187b (Ready; `ToolCall.call_id`/`started_at` and per-call durations). 196 is independent.

**Doctrine functions served**: action (Ze does multi-step read work in one step), learning (repeated scripts become procedure candidates), governance (every inner call is gated, traced and capped exactly like a direct call).

**Owning packages** (for planning): ze-agents (script tool contract, inner-call dispatch through `call_tool`, trace types), ze-workspace (script runner, stub generation, sidecar client), `sidecar/workspace` (script run mode and request/reply channel), ze-memory (procedure candidate source), ze-core (trace build), ze-api (trace REST schema), ze-web (trace instrument for a script step), ze-eval (round-trip assertion). Migration only if planning finds the script source cannot live on the trace (expected: none).

## Context

Today a model that needs five reads makes five tool calls, each its own model round trip, and every intermediate result lands in its context. A script that calls the five reads, joins and filters the results, and returns a short answer replaces those round trips with one.

What the code allows today (verified 2026-10-18):

1. **The sandbox.** `sidecar/workspace` runs commands as an unprivileged user with Python 3.12, a 120 s timeout, an 8,000-character output preview, secrets stripped from the environment, and private and loopback networks dropped. Public internet is reachable. One run at a time (`409 busy`); Ze refuses a second run before it reaches the sidecar (`_refusal_if_busy`).
2. **No way back into Ze.** Code in the sandbox cannot reach Ze: no socket, no callback URL, no token. That is a security property to keep. A run's input is fixed at start (`stdin_b64`), and output is a one-way event stream (`GET /runs/{id}/events`).
3. **Gates.** Every tool call goes through `BaseAgent.call_tool`: retry refusal, the 181 write gate (park, approve, run exactly the approved call), hooks, the tool-call cap (`ToolCallCapHook`, 20 per turn), undo payloads (180). Reads pass without asking. A script must not open a path around any of this.
4. **Workspace gate.** A conversation-origin `workspace_run` asks the user first (`WorkspaceGate`: CONVERSATION × RUN → CONFIRM), because a command can change files and reach the internet.
5. **Tool schemas.** Every `@tool` builds a JSON schema from its Python signature, with injected dependencies hidden. Return values are untyped.
6. **Procedures.** `submit_procedure_candidate` admits a candidate for review; `invoke_procedure` narrows tools but runs no steps. `candidate_from_workspace_run` exists with no production caller.
7. **Eval.** The runner reports `llm_calls` per scenario from `llm_cost_log` but asserts nothing about it.

## Clarifications

### Session 2026-10-18

User answered all recommended (relayed by the Maestro). Limits as proposed.

- Q: How do writes work in a script? → A: the script returns the writes it proposes; Ze runs each after the script ends as a normal tool call through the 181 gate (park, confirmation, undo payloads, Retry unchanged). A write tool called from inside the script is refused with `writes_must_be_proposed`. The stub therefore holds read tools only.
- Q: Sandbox mode and asking first? → A: script runs never ask. They run as a separate sandbox user with all network egress dropped and a throwaway scratch directory removed when the run ends, so the only effects are the gated tool calls.
- Q: Which agents? → A: (revised by the user after Gauge M-2, 2026-10-18) no opt-in list: the script tool is a general harness capability of every agent, offered whenever the agent's visible tools include at least one data read tool (write tools and tools that draw on screen are never data reads). Build T001 (2026-10-18) found the companion has one data read tool, `get_briefing`, so under this rule it gets the script tool in this phase, though with a single read its scripts can do little; cross-agent reads for it remain the follow-up read-bridge phase the Maestro is proposing (not specified here).
- Q: Procedure reuse? → A: three successes of the same script propose a procedure candidate; invoking an approved script procedure runs its stored source through the same script tool, with the stub built from the tools the agent has at invocation time. "Same script" (user, after Gauge Me-4, 2026-10-18): same agent and same ordered list of tools called (the tool signature); the candidate keeps the latest successful script; the user reviews every candidate in Mind › Procedures before use.
- Q: Run slot? → A: a separate script slot in the sidecar: one script may run beside one workspace run; a second script is refused `sandbox_busy`.

## Design decisions

These follow from the facts above and are not open:

- **Ze always initiates.** Ze opens one connection to the sidecar per script (a WebSocket on the sidecar, authenticated like every sidecar endpoint). The script asks for a tool by writing a framed request on a dedicated pipe; the sidecar relays it to Ze over that connection; Ze runs the tool through `call_tool` as the calling agent and sends the reply back the same way. The sandbox never connects to Ze and holds no Ze credential.
- **The stub is generated per run** from the calling agent's visible tools at that moment (its declared read tools, intersected with skill and procedure narrowing, minus server tools, `delegate_to_agent`, the workspace tools and the script tool itself). A name outside that set is refused inside Ze even if the script forges a request.
- **Inner calls are ordinary tool calls.** Each one is a `ToolCall` with its own `call_id`, the script step's `call_id` as parent, 187b timing, gate outcome and undo payload. It counts against the turn's tool-call cap.
- **Python only.** The stub module is `ze_tools`; each function takes keyword arguments matching the tool's schema and returns the tool's result as JSON-decoded data (a string when the tool returns text).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One script replaces a chain of reads (Priority: P1)

The user asks "what did I spend by merchant this month; top five?". Instead of a tool call per account and per page of transactions with every result in context, the finance agent writes one script: list accounts, read each account's transactions for the month, group by merchant, sort, return five lines. The model sees only the five lines.

**Why this priority**: it is the point of the phase: fewer round trips and tokens on multi-step reads.

**Independent Test**: with the sidecar faked, a script that calls two read tools in a loop returns a computed result; the agent's model is called twice in total (write the script, answer), each inner call is on the trace under the script step, and the script source is stored on the trace.

**Acceptance Scenarios**:

1. **Given** an agent with the script tool and three read tools, **When** the model calls the script tool with a script that calls each read tool and returns a summary, **Then** Ze runs each inner call through the normal tool path, the model receives only the script's return value (capped like any tool result), and the trace shows one script step holding three inner calls with durations.
2. **Given** a script that calls a tool the agent does not have, **When** the request reaches Ze, **Then** the inner call is refused with `tool_not_available`, the script receives that error as an exception, and the trace records the refusal.
3. **Given** a skill narrows the agent to two tools, **When** the stub is generated, **Then** it contains only those two tools (if they are reads) and nothing else.
4. **Given** a script raises an exception, exceeds a limit or prints malformed requests, **When** it ends, **Then** the model receives a structured error (`kind`, `message`, the inner calls completed so far, the last 20 lines of stderr) and no partial result is presented as success.

---

### User Story 2 - Limits stop a runaway script (Priority: P1)

A script cannot run forever, call tools without end or spend without end. Each limit ends the script cleanly with a structured error the model can act on.

**Why this priority**: autonomy without limits is the main risk of the feature.

**Independent Test**: one test per limit (wall time, inner-call count, spend, output size) ends the script with its named error and leaves the turn usable.

**Acceptance Scenarios**:

1. **Given** a script still running at the wall-time limit, **When** the limit passes, **Then** the sandbox kills it and the model receives `limit: wall_time` with the calls completed.
2. **Given** a script that makes more inner calls than the per-script cap, or would push the turn past the turn's tool-call cap, **When** the next call arrives, **Then** Ze refuses it with `limit: inner_calls`, and the script ends.
3. **Given** inner calls that themselves cost model spend (a tool that calls a model), **When** the script's attributed spend passes the per-script budget, **Then** further inner calls are refused with `limit: spend`.
4. **Given** a script whose return value is larger than the result cap, **When** it returns, **Then** the model receives the truncated value marked as truncated.

---

### User Story 3 - Writes in scripts never skip the gate (Priority: P2)

A script may need to act on what it read ("archive every newsletter older than a month"). Writes go through the same 181 gate as a direct call: an irreversible write always asks first, a reversible write records its undo payload, and Retry (180) can undo it. The script returns the writes it proposes, and Ze runs each one after the script ends as a normal tool call, so the gate, the park and the confirmation frame are unchanged.

**Why this priority**: the brief puts writes second; reads alone deliver the round-trip saving.

**Independent Test**: a script proposing one irreversible and one reversible write ends; the irreversible one parks and produces one `confirm_request` item; the reversible one runs with an undo payload on the trace; both appear under the script step.

**Acceptance Scenarios**:

1. **Given** a script that proposes an irreversible write, **When** the script ends, **Then** the write parks exactly like a direct call and the user sees one confirmation item naming the target.
2. **Given** a script running in Retry mode proposes an irreversible write, **When** Ze handles it, **Then** it is refused as in 165/180.
3. **Given** a script that calls a write tool directly through the stub, **When** the request reaches Ze, **Then** it is refused with `writes_must_be_proposed`, never executed.
4. **Given** a turn already at the write-confirmation round cap, **When** a script proposes writes, **Then** they are refused `refused_over_cap` as for direct calls.

---

### User Story 4 - The trace shows the script and every call inside it (Priority: P2)

On the trace, a script step shows its source, its outcome, its duration, its limits, and each inner call nested under it with timing and gate outcome. Retry's undo plan and the confirmation summary see inner calls the same way they see direct calls.

**Why this priority**: accountability. A script that hides its calls would be a regression from today's trace.

**Independent Test**: REST trace and `trace_update` carry the script step with `source`, `outcome`, `inner_call_ids`; inner calls carry `parent_call_id`; the web Tools instrument draws the script as one row that expands to its calls and the source.

**Acceptance Scenarios**:

1. **Given** a finished script with three inner calls, **When** the trace is read, **Then** the script step and its three calls appear in call order with `parent_call_id` linking them.
2. **Given** a script source longer than the stored cap (8,000 characters), **When** it is stored, **Then** the trace keeps the first 8,000 characters and says it was cut.
3. **Given** an inner reversible write ran, **When** the user retries the reply, **Then** the rollback plan lists that write like any direct reversible call.

---

### User Story 5 - A script that keeps working becomes a procedure (Priority: P3)

When scripts with the same tool signature (same agent, same ordered list of tools called) succeed three times in a row, Ze proposes the latest one as a procedure candidate for review in Mind › Procedures, with the runs as evidence. Invoking an approved procedure runs its stored script through the same script tool, under the same gates and limits, instead of having the model write it again.

**Why this priority**: it turns repeated work into reusable work, but only after the core path is proven.

**Independent Test**: three successful runs with one tool signature submit exactly one candidate citing the three runs (each run its own ledger record); a fourth success adds no duplicate; a failure resets the count.

**Acceptance Scenarios**:

1. **Given** three successful runs with the same tool signature by the same agent, **When** the third ends, **Then** one candidate is submitted with the latest source as its step, the tools called as its limits, and the three runs as evidence.
2. **Given** a candidate already pending or a procedure already validated for that signature, **When** another success arrives, **Then** nothing new is submitted.
3. **Given** a validated script procedure, **When** the agent invokes it, **Then** the stored script runs with the stub built from the tools the agent has now (never the tools it had when the script was learned), so a procedure never grants a tool.

### Edge Cases

- The sidecar is down or busy: the script tool returns `sandbox_unavailable` or `sandbox_busy` at once; the model can fall back to direct calls.
- A script prints ordinary text as well as framed requests: ordinary output goes to the stderr tail in an error, or is dropped on success; only the declared return value reaches the model.
- A forged or malformed request line: refused with `bad_request`, counted as an inner call attempt, never executed.
- An inner call raises: the script gets an exception carrying the tool's error string, exactly what the model would have seen.
- Concurrent inner calls (threads in the script): requests are handled one at a time in arrival order; the stub is synchronous.
- The user cancels the turn: the script is killed and inner calls in flight finish or are abandoned the way a direct call is.
- The companion asks for a cross-agent join: its only data read is `get_briefing`, so a script cannot reach other agents' data; it delegates as today. Cross-agent reads for scripts come in a follow-up phase through a read bridge.
- An agent with no data read tool (research: server tools and render tools only; also priority, ingestion and prospecting, whose one URL-taking read is `egress`) gets no script tool.
- A read tool that reaches a caller-chosen URL (for example `browser_extract`): it carries the `egress` flag and is never in the stub, so a script cannot reach the network through a tool; the model can still call it directly as today.
- Unattended runs (goal and workflow steps) do not get the script tool in this phase: only conversation turns wire a script runner, and the tool is hidden when no runner is wired. A later phase can extend it with the 181 pre-approved writes rules.
- A tool whose result is not JSON-serializable: the stub receives its string form, as `_serialise_result` gives the model today.
- Server tools (`openrouter:*`) and `delegate_to_agent` are never in the stub; they run on OpenRouter's side or start another agent.
- A script prints: stdout is discarded; only `finish(...)` reaches the model.
- A script allocates memory, forks or fills the disk: the resource limits end it `resource_limit`; every process of the script user is killed.
- A script tries to draw on screen: UI tools are not in the stub; a forged request is refused `tool_not_available`.
- A script with 20 reads then proposes a write: the reads do not count against the turn's tool-call cap, so the write still reaches the 181 gate.
- A reply that contains a script step is retried: the step reads as a read on the trace (`access: script`), so Retry eligibility is decided by the proposed writes as for direct calls.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Ze MUST offer one script tool (working name `run_tool_script(source)`) as a capability of every agent, with no opt-in: it appears when a script runner is wired for the turn and the agent's data read tools (FR-003) number at least one. It runs `source` as Python in the workspace sandbox with a generated `ze_tools` module. Per build T001: calendar, finance, goals, loops, messenger, news, reminders, workflow and the companion (`get_briefing`) get it; research, priority, ingestion and prospecting do not.
- **FR-002**: The script MUST reach Ze only through framed requests on a dedicated pipe, relayed by the sidecar over a connection Ze opened and answered by Ze over the same connection. The sandbox MUST hold no Ze credential and open no connection to Ze.
- **FR-003**: The stub MUST contain exactly the calling agent's **data read tools** at that moment: its visible tools (declared ∩ skill narrowing ∩ procedure narrowing) minus write tools, tools that draw on screen (`produces_ui`: every `render_*` and `show_*` tool), tools that reach a caller-chosen URL or host (`egress`: `browser_extract` today), server tools, `delegate_to_agent`, `invoke_procedure`, workspace tools and the script tool. The script tool is offered only while that set has at least one tool. Ze MUST re-check every request against that set.
- **FR-004**: Every inner call MUST run through `call_tool` as the calling agent, with its gates, hooks, retry rules, cap and undo handling unchanged, and MUST be recorded as a `ToolCall` with `parent_call_id` set to the script step's `call_id`.
- **FR-005**: Writes MUST follow the 181 gate. The script's return value MAY carry proposed writes (tool name and arguments); after the script ends Ze runs each through `call_tool` as a direct call of the calling agent, recorded with `parent_call_id`. A write requested from inside the script MUST be refused with `writes_must_be_proposed`. The stub MUST hold read tools only.
- **FR-005a**: Script runs MUST NOT ask the user first. They MUST run as a dedicated sandbox user with network egress rejected (rule verified at startup and probed per script), no access to `/workspace` (mode set at startup, probed per script), resource limits (memory 256 MiB, 32 processes, 16 MiB per file, CPU time = wall time + 1 s, 64 open files, 32 MiB scratch), stdout discarded, in a scratch directory outside `/workspace` deleted when the run ends, with every process of that user killed at the end, in a script slot separate from the workspace run slot (one script at a time; a second is refused `sandbox_busy`). The script endpoint MUST refuse when no sidecar token is configured. When isolation cannot be verified, scripts MUST be unavailable (fail closed).
- **FR-006**: Limits MUST be configurable with defaults: wall time 30 s, 20 inner calls per script, 10 proposed writes, $0.05 attributed spend per script (checked between inner calls, so one call can overshoot), 4,000-character return value, 8,000-character stored source; fixed caps: 256 KB per request line, 1 MiB per reply or finish value, 2,000 characters of each inner result stored. Inner calls count against the script's cap, not the turn's tool-call cap; proposed writes count against the turn's cap as normal calls. Each limit MUST end the script with a structured error naming it.
- **FR-007**: A failed script MUST return a structured error: `kind` (`exception`, `limit`, `resource_limit`, `sandbox_unavailable`, `sandbox_busy`, `bad_request`, `source_too_long`, `procedure_not_script`), `message`, completed inner calls (name, success), the last 20 lines of stderr, and on `exception` the shape (type and top-level keys) of the last successful inner result.
- **FR-008**: The trace MUST carry the script step (`source` capped and marked when cut, `outcome`, `duration_ms`, limit hit if any) and each inner call linked to it by `parent_call_id` and each inner call with `parent_call_id`, on REST and on `trace_update`. The web trace Tools instrument MUST show the script as one expandable row with its source and inner calls.
- **FR-009**: Retry eligibility, the rollback plan and confirmation summaries MUST treat inner calls exactly like direct calls.
- **FR-010**: Three consecutive successes with the same tool signature by the same agent MUST submit one procedure candidate through `submit_procedure_candidate`, citing the three runs (one ledger record per run); duplicates MUST NOT be submitted. Invoking a validated script procedure MUST run its stored source through the script tool with the stub built from the agent's tools at invocation time; procedure guidance MUST show a script procedure as one line pointing to `run_tool_script(procedure_id=...)`, never its source.
- **FR-011**: The eval scenario format MUST gain an assertion on model calls per scenario (`max_llm_calls`), and three scenarios (finance, messenger, calendar) MUST show a multi-step read finishing in fewer model calls with the script tool than the direct-call baseline. Live runs need the user's OK.
- **FR-012**: The decision record in `research.md` ("Decision record") MUST record: Ze-initiated channel, no sandbox credential, stub equals visible tools, inner calls are ordinary calls, why a hosted sandbox is refused.
- **FR-013**: Public docs MUST describe the feature: `docs/architecture.md` (the script path), `docs/configuration.md` (limits), `docs/sdk.md` (how a tool appears in a script; untyped returns), `sidecar/workspace/README.md` (the script mode and endpoint).

### Key Entities

- **Script step**: one call of the script tool: source, outcome, duration, limit hit; its inner calls point to it by `parent_call_id`.
- **Inner call**: an ordinary `ToolCall` with `parent_call_id`.
- **Tool stub** (`ze_tools`): generated per run from visible tools; never stored.
- **Script procedure candidate**: a procedure candidate whose step is the latest successful script source for a tool signature, with the script runs as evidence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the three multi-step read eval scenarios (finance, messenger, calendar), the script path uses at least 40% fewer model calls than the direct-call baseline (mocked in unit tests; live only with the user's OK).
- **SC-002**: 100% of inner calls appear on the trace with a parent link, timing and gate outcome.
- **SC-003**: 0 tool calls reach execution outside the calling agent's visible set, in a test that forges requests for every registered tool the agent lacks.
- **SC-004**: 0 irreversible writes run from a script without the user's approval, across the write tests.
- **SC-005**: Each limit (wall time, inner calls, proposed writes, spend, result size, request/reply size, memory, processes, file size, scratch size) ends a script with its named error in 100% of its tests, and the turn still answers.
- **SC-006**: Three successful runs with one tool signature produce exactly one procedure candidate, against the real ledger idempotency path.

## Assumptions

- Scripts are short-lived (seconds); a script never detaches into a follow-up turn the way a long `workspace_run` does.
- The per-script spend is attributed from cost rows tagged with the inner calls' ids (the 187b recorder); tools that make no model call cost nothing.
- Stub signatures come from tool schemas; return values stay untyped (JSON data or string). Typed returns are out of scope.
- The sidecar gains one script endpoint (a WebSocket Ze opens), a script sandbox user with no network, and a script slot beside the run slot; the workspace run path, its network rules and its secret stripping stay as they are.
- Normalized source (whitespace and comments stripped, literal values kept) is used for the trace hash and the candidate name only; the learning key is the tool signature.
- 187b lands before this phase is built.
