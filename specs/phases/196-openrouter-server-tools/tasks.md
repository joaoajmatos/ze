# Tasks: OpenRouter Server Tools

**Input**: [spec.md](./spec.md) (clarified 2026-10-18), [plan.md](./plan.md) (Lane Plan), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/server-tools.md](./contracts/server-tools.md), [quickstart.md](./quickstart.md).

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. No real OpenRouter calls; the tee is fed recorded response bodies.

**Build gate**: starts after 187b has landed on `main` (the turn recorder `TurnTelemetry` and its ContextVar are 187b's). No migration.

## Format: `[ID] [P?] [Lane] [Story] Description`

- **[Lane]**: `[L:lead]`, `[L:loop]`, `[L:counts]`, `[L:research]`, `[L:cut]`, `[L:web]`, `[L:docs]` (plan.md Lane Plan). A task touches only files its lane owns.
- **[Story]**: US1 read a named page, US2 allowlist, US3 counts on the trace, US4 docs.

**Crew**: Sonnet `lead`, `loop`, `counts`, `research`, `web`; Haiku `cut` (fully specified deletion) and `docs`. Contract step first; then lanes run in parallel in their own worktrees; `lead` merges loop → counts → research → cut → web → docs. Tick a task's checkbox in the same commit that finishes it.

**Rules for every lane**: `graphify affected` and `rtk proxy grep` before changing a shared symbol; typed `ZeError`s; `get_logger(__name__)`; `git add <paths>`, never `-A` or `stash`.

---

## Phase 1: Setup

- [ ] T001 [L:lead] Branch from `main` after 187b landed. `make install`; `graphify update .`; `graphify affected` on `agentic_loop`, `validate_registry`, `CostTracker`, `TurnTelemetry`, `MessageTrace`, `BaseAgent.stream`. Grep `token_queue`, `def stream(self, ctx`, `_OPENROUTER_TOOL_SCHEMAS`, `_is_openrouter_server_tool`, `_canonical_openrouter_tool_name`, `capture_citations`, `:online` across the repo. Re-read OpenRouter's web-fetch page and confirm the parameter names in [research.md](./research.md) R1. Record differences from plan.md "Blast radius" in the Handoffs note and report them to the Spec Architect (Lintel) before T002.

---

## Phase 2: Foundational (contract step, lane `lead`)

- [ ] T002 [L:lead] Tests first `core/contracts/ze-agents/tests/test_server_tools.py`: `SERVER_TOOLS` has exactly `openrouter:web_search` and `openrouter:web_fetch`; `server_tool_schema("openrouter:web_search", ServerToolConfig())` is `{"type": "openrouter:web_search"}`; the fetch schema carries `engine`, `max_uses`, `max_content_tokens` from the config (defaults `openrouter`, 5, 8000); `ServerToolConfig.from_config` reads `openrouter.server_tools.web_fetch`, falls back per field on a missing block, a wrong type, `max_uses < 1` or `max_content_tokens < 500` (with a warning); `is_server_tool` is true for `openrouter:x`, `openrouter_x` and `openrouter`; `canonical_server_tool_name("openrouter_web_fetch") == "openrouter:web_fetch"` and bare `openrouter` stays `openrouter`; `is_allowed_server_tool` is false for `openrouter:shell` and bare `openrouter`; `server_tool_result_text` returns `[search complete]` and `[page fetch complete]`. See them fail.
- [ ] T003 [L:lead] Implement `core/contracts/ze-agents/ze_agents/server_tools.py` per plan.md "Design / ze_agents/server_tools.py" and [data-model.md](./data-model.md) until T002 passes.
- [ ] T004 [L:lead] Re-export `ServerToolConfig` from `packages/ze-sdk/ze_sdk/__init__.py`; extend the ze-sdk export test if one lists names.
- [ ] T005 [L:lead] Tests first, then add `server_tools: dict[str, int] = field(default_factory=dict)` to `MessageTrace` (`ze_core/conversation/messages/types.py`), `server_tools: dict[str, int] = {}` to `MessageTraceResponse` (`ze_api/api/v0/messages/schemas.py`) and to the `trace_update` schema (`ze_api/api/ws/schemas.py`); `interface/native.py` sends it on the final `trace_update` frame. Tests: trace JSON round-trip keeps the map; an old trace without the key reads as `{}`; REST and the final frame carry it.
- [ ] T006 [L:lead] Regenerate `@myguyze/ze-client` (`make codegen`) and commit the generated diff.
- [ ] T007 [L:lead] Add the `openrouter.server_tools.web_fetch` block to `apps/ze-api/config/config.yaml` exactly as in [data-model.md](./data-model.md); `apps/ze-api/tests/test_config_server_tools.py` loads the real file (copied to `tmp_path` per the settings-fixture rule) and gets the defaults through `ServerToolConfig.from_config`.

**Checkpoint**: contract merged; lanes start.

---

## Phase 3: User Story 2 - Ze requests only the server tools it allows (P1)

**Goal**: one allowlist, enforced at startup and in every request; the dead streaming path gone.

**Independent test**: registry rejects `openrouter:shell`; a sweep over all registered agents finds no request carrying a non-allowlisted or undeclared server tool; `:online` appears nowhere.

- [ ] T008 [P] [L:loop] [US2] Tests first in `core/contracts/ze-agents/tests/test_registry.py`: one parametrized test per refused name (`openrouter:advisor`, `subagent`, `fusion`, `shell`, `bash`, `apply_patch`, `image_generation`, `tool_search`, `experimental__search_models`, `files`, `datetime`) declared on a fake agent makes `validate_registry` raise `AgentConfigError` naming the agent, the tool and both allowed names; `openrouter:web_fetch` and `openrouter:web_search` pass. Implement in `ze_agents/bootstrap.py`.
- [ ] T009 [L:loop] [US2] Tests first in `core/contracts/ze-agents/tests/test_base_agent_loop.py`: (a) the loop builds server tool schemas through `server_tool_schema` with the `server_tools` config passed to `agentic_loop` (and defaults when `None`); (b) a returned `openrouter_web_fetch` call is recorded as a read `ToolCall` named `openrouter:web_fetch` with tool message `[page fetch complete]`; (c) a returned `openrouter:shell` call is recorded with `success=False`, `error="unexpected_server_tool"`, tool message `[error: unexpected_server_tool]`, and a warning log; (d) `_model_args` and `_merge_deps` pass server tool args through unchanged. Implement in `ze_agents/base_agent.py`: delete `_OPENROUTER_TOOL_SCHEMAS`, `_is_openrouter_server_tool`, `_canonical_openrouter_tool_name`; import from `ze_agents.server_tools`; add the `server_tools` parameter. Update the `delegate.py` docstring.
- [ ] T010 [L:loop] [US2] Test `core/contracts/ze-agents/tests/test_server_tool_sweep.py`: import every agent module listed by every plugin's `agent_module_paths()` plus the core agents, run each agent class's declared tools through the loop's schema build with a capturing fake client, and assert each `openrouter:*` entry sent is allowlisted and declared by that agent (SC-003). Mark `slow` only if imports need the embedding model.
- [ ] T011 [L:loop] [US2] Tests first: a new `core/engine/ze-core/tests/orchestration/test_execute_no_streaming.py` asserts `execute_tool` with a `token_queue` key in `config["configurable"]` still runs the agent through `run()` and never calls a `stream` attribute (no existing ze-core test references `token_queue`, grep 2026-10-18). Delete the `token_queue` read in `execute_tool`, the parameter from `_execute_single`, `_execute_compound`, `_run_with_timeout` and `_run_agent`, and the `_stream_and_collect` branch (`orchestration/nodes/execution.py`); delete `BaseAgent.stream` from `base_agent.py`.
- [ ] T012 [L:loop] [US2] Test `core/contracts/ze-agents/tests/test_no_online_suffix.py`: walk `core/`, `plugins/`, `apps/ze-api/`, `packages/ze-sdk/` `*.py` and `*.yaml` (excluding tests and `.venv`) and assert no string literal ends in `:online` (SC-004). It fails until T016 lands; mark it `xfail(strict=True)` with reason "research stream() removed in T016" and drop the mark in T016.
- [ ] T019 [L:cut] [US2] Delete the `stream()` method (and imports it alone used) from: `core/arbitration/ze-priority/ze_priority/agent.py`, `core/automation/ze-automation/ze_automation/agents/goals/agent.py`, `core/automation/ze-automation/ze_automation/agents/workflow/agent.py`, `core/cognition/ze-worldstate/ze_worldstate/agents/agent.py`, `plugins/ze-calendar/ze_calendar/agents/calendar/agent.py`, `plugins/ze-calendar/ze_calendar/agents/reminders/agent.py`, `plugins/ze-finance/ze_finance/agents/finance/agent.py`, `plugins/ze-messenger/ze_messenger/agents/messenger/agent.py`, `plugins/ze-news/ze_news/agents/agent.py`, `plugins/ze-personal/ze_personal/agents/companion/agent.py`, `plugins/ze-prospecting/ze_prospecting/agents/agent.py`. Delete the tests that call those methods in `core/automation/ze-automation/tests/goal_agent/test_goal_agent.py`, `core/automation/ze-automation/tests/workflow_agent/test_agent.py`, `plugins/ze-calendar/tests/agents/calendar/test_calendar_agent.py`, `plugins/ze-calendar/tests/agents/reminders/test_agent.py`, `plugins/ze-messenger/tests/agents/messenger/test_messenger_agent.py`, `plugins/ze-personal/tests/agents/companion/test_companion_agent.py`. Do not touch the research agent (T016) or `openrouter/client.py`'s own `stream`. Gate: `rtk proxy grep -rn "def stream(self, ctx" core plugins` prints nothing and `make test-py` passes.

---

## Phase 4: User Story 1 - Read a page the user names (P1) 🎯 MVP

**Goal**: the research agent fetches a named URL through OpenRouter and answers from it.

**Independent test**: mocked research turn sends both server tools with Ze's fetch config and cites the page.

- [ ] T016 [L:research] [US1] Tests first in `plugins/ze-personal/tests/agents/research/test_research_agent.py`: `ResearchAgent.tools` contains `openrouter:web_fetch`; `run` passes `server_tools=ServerToolConfig.from_config(settings.config)` to `agentic_loop` (a config with `max_uses: 2` reaches the schema); the system prompt contains the when-to-fetch, out-of-reach, data-not-instructions and page-cut-short lines; the completion log carries `fetch_count`; the two `:online` tests are deleted. Implement in `plugins/ze-personal/ze_personal/agents/research/agent.py` (delete `stream()`); import `ServerToolConfig` from `ze_sdk`. Drop the `xfail` mark from T012's test.
- [ ] T017 [L:research] [US1] Tests first: a loop-level test with a fake client whose reply cites a fetched URL (`url_citation` annotation) shows the URL on `AgentResult.sources`; a fetch failure result (`status: failed`) leads to a reply the fake model writes saying the page could not be read (prompt contract only; no model judgment in unit tests). Implement any wiring gaps in the research agent.
- [ ] T018 [L:research] [US1] Add two scenarios with tag `research_fetch` to `eval/scenarios/research.yaml`: a public URL with a question (`expected_agent: research`, `expected_tools: [openrouter:web_fetch]`, criteria: answers from the page, cites the URL); a 404 URL (criteria: says it could not read the page, invents no content). Gate offline with `make test-eval` (the scenario loader, `core/ops/ze-eval/tests/test_scenario.py`, parses every file); do not run live without the user's OK.

---

## Phase 5: User Story 3 - See server tool use on the trace (P2)

**Goal**: `MessageTrace.server_tools` holds OpenRouter's reported counts, summed over the turn.

**Independent test**: a recorded body with `server_tool_use` produces the map on REST, the final frame and the web line.

- [ ] T013 [P] [L:counts] [US3] Tests first `core/engine/ze-core/tests/openrouter/test_citations.py` (rename the module's subject to the raw capture): a non-stream body with `usage.server_tool_use: {"web_search_requests": 2, "web_fetch_requests": 1}` yields `capture.server_tools == {"web_search": 2, "web_fetch": 1}`; an SSE stream whose final usage chunk carries the field yields the same; a body with annotations still yields sources; `"x_requests": -1` and `"y_requests": "3"` are ignored; a key without `_requests` is kept as is. Implement `RawCapture` and `capture_raw()` in `ze_core/openrouter/citations.py` (rename `capture_citations`; no alias).
- [ ] T014 [L:counts] [US3] Tests first `core/engine/ze-core/tests/openrouter/test_client.py`: `complete_with_tools` and `stream_complete_with_tools` call `cost_tracker.record_server_tools({"web_search": 2})` once when the capture holds counts and not at all when empty; sources still reach `source_sink`. Implement in `ze_core/openrouter/client.py`.
- [ ] T015 [L:counts] [US3] Tests first `core/engine/ze-core/tests/telemetry/`: `CostTracker.record_server_tools` forwards to the current `TurnTelemetry.add_server_tools`; with no recorder it logs and does not raise; adds from two delegate tasks sum; an add after `freeze()` is dropped; `stamp` sets `trace.server_tools`; a paused and resumed turn keeps counts from both runs. Implement in `ze_core/telemetry/tracker.py` and `ze_core/telemetry/turn.py`.
- [ ] T020 [P] [L:web] [US3] Tests first `apps/ze-web/src/widgets/assemble/lib/server-tools.test.ts`: `serverToolLines({web_search: 2, web_fetch: 1})` returns `["Web search ×2", "Read page ×1"]` in key order; an unknown key `files` returns `"files ×3"`; `{}` returns `[]`. Implement `widgets/assemble/lib/server-tools.ts`.
- [ ] T021 [L:web] [US3] Tests first `ToolsTimeline.test.tsx`: a trace with `server_tools` renders one line per kind in the instrument's text style; an empty map renders no line and no empty container. Implement in `widgets/assemble/ui/trace/ToolsTimeline.tsx` using the generated type field. `make test-web` and `make typecheck-web` pass.

---

## Phase 6: User Story 4 - The user knows which OpenRouter tools to switch off (P3)

- [ ] T022 [L:docs] [US4] Write the gateway ADR amendment in `specs/arch/openrouter-gateway.md` (plan.md "Docs"); the `docs/configuration.md` "OpenRouter server tools" section (allowlist, the `openrouter.server_tools.web_fetch` block, the tools to switch off in the OpenRouter workspace settings with one reason each, the locked-mode 403 and regional 403); `docs/sdk.md` (both tools, the startup error, page text is untrusted); `docs/architecture.md` (one sentence: server tool counts reach the trace, if its trace section lists fields). Follow the `doc-style` skill. The refused-tool list must match T008's list exactly (SC-006).
- [ ] T023 [L:docs] [US4] `AGENTS.md`: the "Web search" stack row names both tools; phase row 196; Learned Workspace Facts line "server tools: allowlist in `ze_agents/server_tools.py`". `specs/README.md`: row 196 Implemented. Coverage check: list every public doc touched by `git diff main...HEAD --stat` and every doc that names `openrouter:web_search`, `stream()` on agents or `capture_citations`; each is updated or recorded as needing no change in the Handoffs note.

---

## Phase 7: Polish and cross-cutting (lane `lead`)

- [ ] T024 [L:lead] Merge lanes in order; run `make lint`, `make test-py`, `make test-web`, `make typecheck-web`, `rtk proxy grep -rn ":online" --include=*.py --include=*.yaml core plugins apps packages` (empty). Record results in the Handoffs note.
- [ ] T025 [L:lead] Optional, with the user's OK only: `make dev-eval` and `python eval/run.py --tag research_fetch`; record the result and the `server_tools` counts seen on the trace. Mark the spec status Implemented and set floor status review.

---

## Dependencies & Execution Order

- 187b on `main` → T001 → T002–T007 (contract) → lanes in parallel.
- `loop`: T008 ∥ T009 → T010 → T011 → T012. `cut` T019 starts after T011 merged.
- `research`: T016 → T017 → T018 (T016 removes T012's xfail; merge after `loop`).
- `counts`: T013 → T014 → T015. `web`: T020 → T021.
- `docs` after all lanes merged. T024 → T025.

## Parallel Example

After the contract step: `loop` T008/T009, `counts` T013, `research` T016, `web` T020 start together in separate worktrees.

## Implementation Strategy

MVP = contract + US2 (allowlist) + US1 (fetch). US3 counts and US4 docs complete the phase; the phase is not done without docs.

## Handoffs

Lane leads record blast-radius differences, gate runs and doc coverage in the "Web Overhaul Specs Handoffs" note (or the build floor's note).
