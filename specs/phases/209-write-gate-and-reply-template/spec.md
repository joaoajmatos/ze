# Feature Specification: Write Gate and Reply Template

**Feature Branch**: `209-write-gate-and-reply-template`

**Created**: 2026-10-22

**Status**: Draft

**Input**: User description (approved 2026-10-22, "go ahead with all of it"): architecture review 2026-10-22, candidate C4 together with plugin findings #4 and #6 and engine findings #5 and #6.

- Pull a pure **WriteGate** (run / refuse / park) and a **ToolDispatcher** out of `BaseAgent`.
- `call_tool` loses its private keyword arguments and its `loop_active` ordering rule.
- `BaseAgent.respond()` becomes the reply template, with the honesty guards always on and the guards declared per agent.
- Add a default `stream()` and delete the 12 copies; remove the `token_queue` path.
- `@tool` declares the claim it earns, so `nested_tools`/`honesty` stop hard-coding domain tool names.
- Render guidance is assembled from the tools an agent actually has.
- Run the finance and research evals before turning their guards on.

**Governed by**: phase 165 (Retry write block), phase 181 (irreversible writes ask first; approval is an `ApprovedCall` built only from park state), phase 191a (UI tool actions through `call_tool`), phase 197 (script inner calls through `call_tool`), phases 143–146 and 169 (earned-claim honesty guards), phase 145 (reply gates), `specs/arch/plugin-domain-vocabulary.md` (no plugin vocabulary in core contracts), `specs/arch/pre-v1-hard-cuts.md`, `specs/GLOSSARY.md` (Parked write, Approval, Retry, Undo).

**Depends on**: 200 (AgentContext derivation): the gate reads write-gate state from the context part that phase 200 separates out.

**Doctrine functions served**: governance (every write decision is made in one testable place), action (every agent reply passes the same honesty guards, so Ze never claims an action it did not take).

**Owning packages** (for planning): ze-agents (`base_agent.py`, `tool.py`, `honesty.py`, `nested_tools.py`, new gate and dispatcher modules), every package with an `@agent` (13 agents in ze-worldstate, ze-priority, ze-ingestion, ze-automation (2), ze-finance, ze-news, ze-messenger, ze-personal (2), ze-calendar (2), ze-prospecting), ze-core (`orchestration/nodes/execution.py` token_queue path), ze-components (render guidance text), ze-eval (guard regression scenarios). No migration.

## Context

`core/contracts/ze-agents/ze_agents/base_agent.py` is 1,517 lines. The October cleanup report listed it at about 906.

- **`call_tool` carries about nine concepts in one interface** (`base_agent.py:408-635`):
  - the Retry block;
  - user approval;
  - plan pre-approval;
  - the constraint veto;
  - `ask_check`;
  - asks-first;
  - the write round cap (`:521`);
  - parking and building the `ParkedWrite`;
  - hooks, undo split, trace id and the tool sink.
- **Its signature exposes five private keyword arguments** (`_iteration`, `_lm_args`, `_call_id`, `_approval`, `_trace_call_id`, `:408-417`).
- **Callers must set `ctx.loop_active` first,** or an asks-first tool raises `AgentConfigError` (`:528-531`). `run_action` does this by hand (`:392-404`), and so does `agentic_loop` (`:800`). `run_undo` passes `_approval=ApprovedCall("undo")` (`:360`).
- **`_run_loop` (`:833-1206`) repeats the same tail** `_finish` + append call + append tool message in five dispatch branches (`:1026, :1045, :1065, :1094, :1143`).
- **Seven production `.call_tool(` call sites:** five in `base_agent.py`, one in `script_step.py`, one in the companion (`plugins/ze-personal/ze_personal/agents/companion/agent.py:269`). There are 79 test call sites.
- **Reply protocol is copied per agent.** 13 agents are registered with `@agent`. Seven run a reply guard, and their protocols differ:
  - `hold_token_sink` → loop → restore → `publish_honest_reply` or `enforce_domain_cancel_confirmations`: calendar, reminders, messenger, news, companion;
  - hand-rolled: worldstate loops, goals.

  Six return the raw model reply: priority, ingestion, workflow, finance, research, prospecting.
- **`stream()` is copied.** 12 agents override `stream()` with the same body that awaits `run` and yields the response: worldstate `agent.py:111`, priority `:92`, goals `:142`, workflow `:120`, finance `:98`, news `:176`, messenger `:121`, research `:87`, companion `:256`, calendar `:125`, reminders `:99`, prospecting `:143`. The base default raises (`base_agent.py:185`).
- **The `token_queue` path is never fed.** It is read at `ze_core/orchestration/nodes/execution.py:299` and threaded to `_run_agent` (`:582`), but no code sets `"token_queue"`. Only that path calls `stream()`.
- **Contracts hard-code domain tool names.**
  - `nested_tools.py` has `cancel_reminder_earned` (`:104`), `abandon_goal_earned` (`:118`), `loop_review_earned` (`:132`, `close_loop`/`drop_loop`), `tracking_earned` (`:149`, `track_loop`/`confirm_loop`) and `turn_creation` (`:182-184`, `set_reminder`/`create_goal`).
  - `honesty.py` has `_earned(calls, "remember_fact"/"forget_fact")` (`:273-274`) and a list of `render_*` tools (`:53-58`).
  - Each new "earned" write means editing ze-agents.
- **Render guidance prose is copied** into agent instructions in finance, research, companion, calendar and goals, with drifting wording.
- **`@tool` has 19 keyword arguments** (`tool.py`). About 12 of them are write-gate policy.

Blast radius: `graphify affected BaseAgent --depth 1` lists about 205 dependents. `publish_honest_reply` has 14 direct references.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every agent's reply is honest by default (Priority: P1)

Any specialist (finance, research, prospecting and the rest) answers through the same reply path. A reply that claims an action no tool earned in that turn ("I've set a reminder", "I'll remember that", "I'm tracking it") is corrected the same way for every agent.

**Why this priority**: today six of thirteen agents can tell the user they did something they did not do. This is the doctrine's honesty rule, and it is the most user-visible gain.

**Independent Test**: one contract test runs every registered agent with a stub model whose reply claims an unearned write, and asserts the guard corrected it.

**Acceptance Scenarios**:

1. **Given** the finance agent replies "I've set a reminder for that" with no reminder tool call, **When** the reply is published, **Then** the unearned claim is removed or corrected exactly as it is for the companion today.
2. **Given** a new agent with no reply code of its own, **When** it is registered, **Then** it gets the guards without its author writing any.
3. **Given** the finance and research eval scenarios, **When** they run with guards on, **Then** they pass at their current rates. Any drop is fixed before the phase closes.

---

### User Story 2 - Write decisions are made in one place (Priority: P1)

Whenever a tool call reaches a write, one decision says whether it runs, is refused (Retry block, veto, over the round cap) or is parked for the user. That decision is the same for a model call, a resumed approval, an undo, a UI action and a script's inner call.

**Why this priority**: phases 165, 181, 191a and 197 each added branches inside `call_tool`. The full matrix (retry × approval × pre-approval × veto × ask-check × asks-first × round cap) can only be tested by running an agent.

**Independent Test**: a table test calls the write gate directly with every combination and asserts run, refuse or park and the reason, with no agent, model or tool body.

**Acceptance Scenarios**:

1. **Given** Retry mode and an irreversible write, **Then** the gate refuses.
2. **Given** an `ApprovedCall` built from park state for the same call, **Then** the gate runs it without asking again.
3. **Given** a fourth write round, **Then** the gate refuses with the over-cap reason.
4. **Given** a UI action or an undo, **When** it reaches the gate, **Then** no caller-side ordering flag is needed.

---

### User Story 3 - A domain package owns the claims its tools earn (Priority: P2)

A plugin adds a write tool and declares the claim the tool earns. The honesty guards recognise a reply that claims that action without ze-agents changing.

**Why this priority**: it stops ze-agents from knowing reminder, goal, loop and memory tool names, and makes the next earned write a one-package change.

**Independent Test**: register a test-only tool that declares an earned claim, and check that the guard treats a reply claiming it as earned only when the tool ran successfully.

**Acceptance Scenarios**:

1. **Given** `track_loop` declares its claim, **When** ze-agents is searched for `"track_loop"`, **Then** nothing is found outside tests.
2. **Given** every existing earned check (reminders, goals, loops, memory), **When** they move to declarations, **Then** their current test cases pass unchanged.

---

### User Story 4 - Agents carry only their own instructions (Priority: P3)

Render-tool guidance and similar shared tool advice reach an agent's prompt because it has those tools, not because its author pasted the paragraph.

**Why this priority**: it removes drift and churn from the hottest agent file (the companion), but it is wording, so it ranks last.

**Independent Test**: build the prompt for an agent with the render tools and one without, and assert the guidance appears exactly once and only for the first.

**Acceptance Scenarios**:

1. **Given** finance, research, companion, calendar and goals, **When** their prompts are built, **Then** the render guidance comes from one source.
2. **Given** the routing and companion eval scenarios, **When** they run, **Then** they pass at their current rates.

### Edge Cases

- An agent intentionally publishes a reply without guards. It is not allowed silently: it must declare why (as asks-first tools declare a no-ask reason), so the exception shows up in review.
- A tool call fails after a write runs. The earned claim counts only on the clean result, as today (`_ok_true`).
- Parallel tool calls in one model turn. Each gets its own gate decision, and the round cap counts rounds, not calls.
- A script inner call proposes a write in `finish(...)`. It goes through the same gate after the script, as phase 197 defined.
- An agent overrides `respond()` for a domain post-step (contact extraction, outreach). The guards still run on the final reply.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST decide every write tool call in one write-gate module. It takes the tool's declaration, the arguments, the write-gate state and an optional approval, and returns run, refuse (with reason) or park (with summary). It MUST NOT call a model or a tool body.
- **FR-002**: The gate's decision MUST cover the Retry block, user approval from park state, plan pre-approval, the constraint veto, `ask_check`, asks-first and the write round cap, with the precedence phase 181 defines.
- **FR-003**: Tool execution MUST go through one dispatcher. It turns one model tool call into an executed call, a transcript message and an optional park. The five duplicated dispatch tails MUST be removed.
- **FR-004**: `call_tool`'s interface MUST NOT expose private keyword arguments. An approval, an undo and a UI action MUST be passed as an explicit, typed approval. No caller may need to set `loop_active` before calling.
- **FR-005**: `BaseAgent` MUST provide one reply template (`respond`): build the prompt, run the loop with buffered tokens, run the guards, publish once. Agents MUST supply only instructions, prompt extras, dependencies and optional post-loop steps.
- **FR-006**: The reply guards MUST run for every agent by default. An agent MAY narrow or extend its guard set by declaration. An agent that turns guards off MUST declare a reason.
- **FR-007**: `BaseAgent` MUST provide a working default `stream()`. The 12 identical overrides MUST be deleted. The unused `token_queue` path in execution MUST be deleted (Principle VIII).
- **FR-008**: A write tool MUST be able to declare the claim it earns. The honesty and nested-tool guards MUST read earned claims from the tool registry, and ze-agents MUST NOT name domain tools.
- **FR-009**: Shared tool guidance (render tools first) MUST be attached to a tool or tool group and assembled into the prompt of any agent that has those tools. The pasted copies MUST be removed.
- **FR-010**: Before the finance, research, prospecting, priority, ingestion and workflow agents get guards, their eval scenarios MUST be run, and any change in their results recorded in the phase handoff.

### Key Entities

- **Write decision**: the outcome of the gate for one call: run (with the approval that licensed it), refuse (with a reason) or park (with a summary).
- **Earned claim**: a declared statement a successful tool call licenses the reply to make (for example "a reminder is set").
- **Reply guard**: a check on the final reply that removes or corrects unearned claims, unsolicited recitation and declined lines.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 13 of 13 registered agents publish through the guarded template. Today 7 do.
- **SC-002**: The write-gate matrix is covered by a table test that needs no agent. Every phase 165/181/191a/197 gate test either moves onto it or still passes.
- **SC-003**: `base_agent.py` loses the write-gate and dispatch logic; its tool-loop section shrinks by at least half.
- **SC-004**: Searching ze-agents for domain tool names (`set_reminder`, `create_goal`, `track_loop`, `remember_fact` and similar) finds nothing outside tests.
- **SC-005**: Exactly one definition of `stream()` exists in agent code.
- **SC-006**: The finance, research, routing and companion eval scenarios pass at or above their pre-phase rates.

## Assumptions

- Phase 200 has split write-gate state (resume, decisions, round, pre-approved writes) off `AgentContext`. If not, the gate reads the current fields, and this phase does not add new ones.
- Token streaming to the client keeps going through `token_sink` (phase 95). Removing `token_queue` removes no live behaviour.
- `@tool`'s existing policy arguments stay declarative. This phase moves their interpretation, not their spelling, apart from adding the earned-claim declaration.
- Prompt wording is eval-sensitive. Any change to an agent's prompt text beyond moving render guidance is out of scope.
