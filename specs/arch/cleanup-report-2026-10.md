# Cleanup Report — 2026-10

> **Status:** Investigation complete. Nothing changed but this file.
> **Date:** 2026-10-16
> **Base:** `main` @ `d70b7af7` (floor `cleanup-investigation`)
> **Author:** Spec Architect (Plinth), Cleanup Investigation floor
> **Next step:** the user picks rows. Cleanup floors branch off `main` after floors 181 and 173 land.

This report lists dead code, unused config, shim residue, dependency-rule breaks, stale docs,
misplaced code, and the `ze-api` route surface. Each row carries evidence and a proposed
cleanup floor (`CF-xx`, §12). §11 ranks the top 20.

## How to read the tables

| Column | Meaning |
|---|---|
| **Conf.** | **confirmed**: a tool found it and grep plus a read of the code agree. **likely**: strong evidence, one open question noted in the row. |
| **Risk** | Risk of the removal or fix. **low**: nothing calls it. **med**: behavior or schema change, or a test needs rework. **high**: user-visible behavior, migration, or a cross-package contract. |
| **Effort** | **S** under 1 hour, **M** half a day, **L** one day or more (one Sonnet lane). |
| **Floor** | Proposed cleanup floor from §12. |
| **⟳ 181 / ⟳ 173 / ⟳ 182** | The row touches an area an in-flight floor changes. Recheck it after that floor lands. |

ComplexityEstimator (`ze_core/routing/complexity.py`) is out of scope: floor 182 deletes it.

## Method

| Step | Tool | Result |
|---|---|---|
| Dead Python code | `uvx vulture core packages plugins integrations apps/ze-api eval scripts sidecar --min-confidence 60` (migrations excluded; one run with tests, one without) | 512 raw hits. A triage script counted every name across the repo (src / tests / docs). 182 had no other reference anywhere, 51 had test-only references. Routes, `@tool`, `@agent`, `@mcp.tool`, `@render_tool`, Pydantic validators, and dataclass/enum members read through rows were dropped as false positives. |
| Confirmation | `graphify update .` then `graphify explain` on ~60 survivors; `git grep -w` | Every row in §1 has zero inbound `calls`/`imports` edges in graphify **and** one grep line (its definition). See §10 for where graphify cannot be trusted. |
| Dead TS | `npx knip@5.62.0` (TS 5.8.3 pinned; node 22) over `apps/ze-web`, `packages/ze-ui`, `packages/ze-client` (generated code ignored) | 21 unused files, 72 unused exports, 86 unused exported types, 24 duplicate exports, 4 unused deps. |
| Config | YAML leaf-key scan of `config/config.yaml` against string reads in non-test source; reverse scan of `.get("key")` chains; Settings fields | §2. |
| Dependencies | AST scan of every package's imports against its `pyproject.toml` `ze-*` deps | §4. |
| Docs | Every backticked path, `*.py` name, symbol and `make` target in `docs/`, root docs, and READMEs, checked against the tree, the Makefile and the code | 146 raw hits; §5 keeps the real ones. |
| Routes | `create_app()` plus static plugin routers; OpenAPI export; callers from the generated SDK function names in ze-web/ze-ui, raw `fetch` paths, eval/scripts/Makefile, and plugin `page_operation_id` | §8. |
| Flake | `sidecar/workspace` suite 30× serial and 60× under 4× parallel load with `ResourceWarning` and `PytestUnraisableExceptionWarning` as errors | §0 item 6. |

---

## 0. Maestro items (Type Cleanup follow-ups)

| # | Item | Status on `d70b7af7` | Evidence | Residual finding | Floor |
|---|---|---|---|---|---|
| 1 | `LLMClient.complete_with_tools` lacks `temperature` | **Fixed** | `16d037a0 LLMClient: add temperature to complete_with_tools contract`; `ze_agents/client.py:36` | `stream_complete_with_tools` has no `temperature` in the Protocol (`client.py:41`) or the real client (`ze_core/openrouter/client.py:168`). The two agree, so this is a gap, not drift. `ze_correlation/engine.py:62` types `llm_client: Any  # ze_agents LLMClient protocol` instead of `LLMClient`. | CF-01 |
| 2 | `ze_core/routing/types.py:55` re-declares `LLMClient` | **Fixed** | `80770b0e Remove duplicate LLMClient Protocol from ze_core.routing`; `routing/types.py` now holds only `SubTask`, `RoutingJudgment`, `RoutingEnvelope`, `RouterConfig` | none | — |
| 3 | `social_cooccurrence.py` / `promotion.py` import `ze_plugin` | **Fixed** for `ze_plugin` | `8d7e3528 Plugins: route ze_plugin and exported ze_memory imports through ze_sdk`; both now import `EvidenceRef` from `ze_sdk.contribution` | Both still import `ze_correlation.types` directly (`promotion.py:13`, `social_cooccurrence.py:14`); `ze-personal` does not declare `ze-correlation`. **Why the test misses it:** `packages/ze-sdk/tests/test_plugin_boundaries.py:7` forbids only `ze_core`, `ze_api`, `ze_plugin` and `ze_memory`. It allows every other core package, so ~200 direct plugin imports of `ze_agents`, `ze_logging`, `ze_proactive`, `ze_communication`, `ze_data`, `ze_automation`, `ze_correlation` pass (§4, D-05). | CF-05, CF-06 |
| 4 | Two `EvidenceRef` dataclasses (correlation vs worldstate) | **Fixed** | `0c95f769 ze-correlation: rename EvidenceRef to HypothesisEvidence`; `4173a7ce ze-worldstate: drop its EvidenceRef, use the contribution seam's`; one class left: `ze_plugin/contribution.py:71` | Two closed kind lists remain: `EvidenceRef.kind` (`fact, episode, signal, ingestion, goal, action_record`) and `HypothesisEvidence.kind` (`fact, episode, signal`, `ze_correlation/types.py:13`). The shared ref lives in `ze_plugin`, not beside the claim vocabulary in `ze_agents/claims.py` that `specs/arch/claim-topology.md` names. Low priority; settle in an ADR note, not a code move. | CF-13 (note) |
| 5 | `ProactiveNotifier` name shared by contract and engine class | **Fixed** | `bb17505d ze-core: delete dead ze_core.proactive package`; one class: `ze_proactive/notifier.py:29`. The ntfy side is `Notifier` (Protocol) and `NtfyNotifier` in `ze-notifications`. | none | — |
| 6 | Flaky `sidecar/workspace` tests: "Event loop is closed" on teardown | **Fixed by `b5721c63`** (2026-10-09); not reproduced | 0 failures in 90 runs (30 serial; 60 under 4 parallel loops with `-W error::pytest.PytestUnraisableExceptionWarning -W error::ResourceWarning`) | **Cause (before `b5721c63`):** tests left a live child at `TestClient` exit (`test_run_returns_immediately_with_id` leaves `sleep 0.2`; `test_one_slot_invariant_409_names_running_handle` cancels `sleep 5` without waiting). The portal's loop closed, then GC ran `BaseSubprocessTransport.__del__` → `close()` → pipe `close()` → `loop.call_soon` on a closed loop → `RuntimeError: Event loop is closed` (CPython 3.12.8 `asyncio/base_subprocess.py:96-126`). The fixture's `_drain_runs` (`tests/conftest.py:31`) now cancels and waits for a terminal status. On 3.12 a pending `proc.wait()` resolves only in `_call_connection_lost` (`base_subprocess.py:241-252`), after the transport is torn down, so a terminal status is now safe. **Residual hardening:** (a) `spawn_run` drops the task from `asyncio.create_task(_execute(...))` (`supervisor.py:486`); keep a module-level task set so GC cannot collect a running task, and let the fixture await it. (b) `main.py:90` uses deprecated `@app.on_event("startup")`; move to a lifespan. (c) If the flake reappears in `make test-py`, record which test ran last. | CF-12 |
| 7 | graphify does not resolve `ze_sdk` re-exports, so `affected` under-reports | **Confirmed, broader than ze_sdk** | `graphify-out/graph.json`: 892 of 23,144 nodes have no `source_file`. These are phantom stubs, one per importing file, for names graphify cannot resolve (re-exports, aliased imports). 374 class-like labels are ambiguous. `graphify explain EvidenceRef` lands on a phantom (degree 0); `graphify affected EvidenceRef` prints "No unique node match". The canonical `GoalStore` node has in-degree 1; ten phantom `GoalStore` nodes hold the importers. `get_logger` shows 23 inbound edges though hundreds of modules call it. | Proposed fix in §10 (T-01). This report's dead-code rows were confirmed with grep and the ze_sdk re-export list, not only graphify. | CF-13 |

---

## 1. Dead code

### 1a. Python — no reference anywhere (definition only)

All rows: vulture hit, `graphify explain` shows no inbound call/import edge, `git grep -w` returns only the definition. ze_sdk re-exports checked (none re-export these names).

| ID | Finding | Evidence | Conf. | Risk | Effort | Floor |
|---|---|---|---|---|---|---|
| X-01 | `Container.invoke_raw()` — engine entry point nobody calls; `invoke_raw_turn` replaced it. Still described in docs (14 doc mentions). | `core/engine/ze-core/ze_core/container.py:191` | confirmed | low | S | CF-07 |
| X-02 | `CoreContainer.preprocessor` field never read | `ze_core/container.py:38` | confirmed | low | S | CF-07 |
| X-03 | 13 unused constants in `ze_agents/defaults.py`: `MEMORY_FACTS_TOKEN_BUDGET`, `MEMORY_EPISODES_TOKEN_BUDGET`, `MEMORY_EPISODES_FETCH_LIMIT`, `MEMORY_CONTRADICTION_THRESHOLD`, `MEMORY_MERGE_SILENT_THRESHOLD`, `MEMORY_MERGE_LLM_THRESHOLD`, `MEMORY_UNREVIEWED_TTL_DAYS`, `MEMORY_CONTRADICTED_TTL_DAYS`, `MEMORY_EXPIRY_GRACE_DAYS`, `MEMORY_EPISODE_RECENCY_DAYS`, `MEMORY_EPISODE_ARCHIVE_BATCH`, `MEMORY_EPISODE_MIN_ARCHIVE_BATCH`, `GOAL_ADVANCE_INTERVAL_SECONDS`. ze-memory keeps its own copies in `ze_memory/defaults.py` (second vocabulary). | `core/contracts/ze-agents/ze_agents/defaults.py:46-97` | confirmed | low | S | CF-01 |
| X-04 | 4 unused constants in `ze_memory/defaults.py`: `DEFAULT_EVENT_BUDGET_TOKENS`, `CONTRADICTION_THRESHOLD`, `EPISODE_RECENCY_DAYS`, `SESSION_SUMMARIES_FETCH_LIMIT` | `core/cognition/ze-memory/ze_memory/defaults.py:3,8,16,32` | confirmed | low | S | CF-03 |
| X-05 | `ze_agents.registry.get_agent_instances()` | `ze_agents/registry.py:85` | confirmed | low | S | CF-01 |
| X-06 | `ze_proactive.job.get_registered_proactive_jobs()` | `core/contracts/ze-proactive/ze_proactive/job.py:23` | confirmed | low | S | CF-12 |
| X-07 | `ze_agents/onboarding/` package (re-exports `ze_onboarding` types). **Zero importers, including tests.** It is the only reason `ze-agents` depends on `ze-onboarding`, so deleting it breaks the `ze-agents ↔ ze-onboarding` cycle (§4, D-01). | `core/contracts/ze-agents/ze_agents/onboarding/__init__.py`, `types.py`; `git grep ze_agents.onboarding` → 0 | confirmed | low | S | CF-01 |
| X-08 | Dream store methods `get_artifacts_by_status`, `get_last_successful_run_at`, `count_artifacts_by_status` | `ze_memory/dream/store.py:115,308,321` | confirmed | low | S | CF-03 |
| X-09 | Dream types: `ReplayCandidate` (+ fields `recency_score`, `confidence_inverse_score`), `DreamRunSummary.artifacts_pending_review`, enum members `COUNTERFACTUAL`, `PERTURBATION_CHECK`, `CRITIC_ONLY` | `ze_memory/dream/types.py:17-81` | likely (enum members may be stored values; check `memory_dream_*` rows before deleting) | low | S | CF-03 |
| X-10 | `MemoryRetriever.upsert_session_summary`, `_link_procedure_to_task` | `ze_memory/retriever.py:770,1170` | confirmed | low | S | CF-03 |
| X-11 | `procedures/admission.version_to_procedure`, `procedures/tools.INVOKE_PROCEDURE_TOOL`, enum members `WITHDRAW`, `PLANNER` | `ze_memory/procedures/admission.py:475`, `tools.py:20`, `types.py:46,208` | likely (enum members) | low | S | CF-03 |
| X-12 | Extractor `DROP_FAMILIES` and family members `PREFERENCE`, `RELATIONSHIP`, `CONTACT_DETAIL` | `ze_memory/extractor.py:27-34` | likely (members may arrive as model output strings) | low | S | CF-03 |
| X-13 | `ActionRecord` `TERMINAL_LIFECYCLES` | `ze_memory/action_records/types.py:19` | confirmed | low | S | CF-03 |
| X-14 | `PostgresHypothesisStore.set_feedback` | `core/cognition/ze-correlation/ze_correlation/store.py:129` | confirmed | low | S | CF-03 |
| X-15 | `GoalSuggestionStore.was_topic_suggested_recently`; goal learning enum members `USER_CORRECTION`, `DERIVES` | `ze_automation/goals/suggestion_store.py:143`, `goals/types.py:124,130` | confirmed (method); likely (members) | low | S | CF-04 |
| X-16 | `ze_core.conversation.retry.DISCONNECTED`; `procedure_activation.intersect_for_invocation` | `ze_core/conversation/retry.py:32`, `ze_core/orchestration/procedure_activation.py:179` | confirmed | low | S | CF-07 |
| X-17 | `DataPortabilityService.get_total_size_bytes` | `core/kernel/ze-data/ze_data/portability/service.py:72` | confirmed | low | S | CF-12 |
| X-18 | `ze_eval.types.ScenarioResult` | `core/ops/ze-eval/ze_eval/types.py:51` | confirmed | low | S | CF-12 |
| X-19 | Workspace: `retry_pending_workspace_action_records`, `WORKSPACE_TOOLS` list, `WorkspaceRunResult` | `ze_workspace/action_handoff.py:87`, `tools.py:40`, `types.py:95` | confirmed | low | S | CF-12 |
| X-20 | Sidecar `RUN_LOCK_WAIT_SECONDS` (and config key `workspace.run_lock_wait_seconds`, §2) | `sidecar/workspace/supervisor.py:17` | confirmed | low | S | CF-12 |
| X-21 | Trading212 write surface never called: `get_orders`, `place_limit_order`, `place_market_order`, `cancel_order`, `get_instruments`. Live order placement in a read-only finance domain is risk with no caller. | `integrations/ze-trading212/ze_trading212/client.py:38-113` | confirmed | low | S | CF-11 |
| X-22 | Finance "risk" scaffolding: `AlphaModel`, `RiskEngine` (`compute_exposures`, `check_drift`), `FactorReading`, 13 `RiskFactor` members; Phase 67 stubs for a future `ze-risk` | `plugins/ze-finance/ze_finance/models/alpha.py:8`, `risk/engine.py:9-15`, `risk/types.py:11-44` | confirmed | low (pre-v1: no speculative scaffolding) | S | CF-11 |
| X-23 | `MessengerPlugin._action_record_store` set, never read; `BriefingJob._persons` set, never read | `plugins/ze-messenger/ze_messenger/plugin.py:59`, `plugins/ze-personal/ze_personal/jobs/briefing.py:46` | confirmed | low | S | CF-11 (messenger), CF-04 (personal) |
| X-24 | `Person.inferred_classification`, `inferred_relationship`; `CoOccurrenceCandidate.existing_hypothesis_id`; `ze_news.types.FlagType` | `ze_personal/contacts/types.py:63-64`, `social/types.py:39`, `ze_news/types.py:7` | likely (fields may be filled by row mapping; check stores) | low | S | CF-04 |
| X-25 | ze-api: dead DI getters `get_openrouter_client`, `get_router`, `get_memory_store`, `get_graph`; `db.dispose_checkpointer_pool`; errors `TranscriptionError`, `ImageDownloadError`; `ActorContextResponse` schema; settings `profile_config`, `active_profile()` | `apps/ze-api/ze_api/api/dependencies.py:40-60`, `db.py:56`, `errors.py:36,40`, `api/schemas.py:704`, `settings.py:105,151` | confirmed | low | S | CF-09 |
| X-26 | `ze_core.routing.judge.QUESTION_IDS` ⟳ 182 | `ze_core/routing/judge.py:30` | confirmed | low | S | CF-14 |

### 1b. Python — reached only from tests

Production never calls these. Each needs a decision: wire it (if the feature is wanted) or delete it with its tests.

| ID | Finding | Evidence | Conf. | Risk | Effort | Floor |
|---|---|---|---|---|---|---|
| T-01 | Goal suggestion accept/dismiss path: `GoalPlanner.create_goal_from_suggestion`, `GoalSuggestionStore.mark_accepted`, `mark_dismissed`, `resolve_short_id` — tests only; no tool, route or job calls them. Users cannot accept a weekly goal suggestion. | `ze_automation/goals/planner.py:744`, `suggestion_store.py:67,85,163` | confirmed | med (feature gap: decide wire vs delete) | M | CF-04 |
| T-02 | `GoalPlanner.promote_learnings` — test-only; Phase 137 replaced it with evidence-backed `goals/learning.py` | `ze_automation/goals/planner.py:495` | confirmed | low | S | CF-04 |
| T-03 | `ze_memory.extractor.merge_fact_proposals` — residue of `AgentResult.memory_proposals` (removed in phase 140); its test lives in ze-core | `ze_memory/extractor.py:209`; test `core/engine/ze-core/tests/memory/test_extractor.py:32` | confirmed | low | S | CF-03 |
| T-04 | `MemoryRetriever._persist_facts`, `search_session_summaries`; `procedures/admission.record_procedure_feedback`, `rollback_procedure`; `procedures/retrieval.project_procedure_history`; `RelevanceScorer.invalidate_cache`; `SleepPass._check_sensitive_entities` | `ze_memory/retriever.py:346,813`, `procedures/admission.py:117,167`, `procedures/retrieval.py:9`, `relevance.py:145`, `dream/sleep_pass.py:148` | confirmed | low | S | CF-03 |
| T-05 | `GmailChannel.poll_replies` — docstring says "Backward-compat thin wrapper around get_thread for prospecting" | `integrations/ze-google/ze_google/gmail_channel.py:163-168` | confirmed | low | S | CF-11 |
| T-06 | `ContactChannelStore.get_preferred` / `set_preferred` | `ze_personal/contacts/channel_store.py:36,73` | confirmed | low | S | CF-04 |
| T-07 | Action-record adapters never wired: `contribution_from_workspace_run`, `candidate_from_workspace_run`, `contribution_from_outbound` | `ze_workspace/action_records.py:115`, `procedure_candidates.py:22`, `ze_messenger/outbound/adapter.py:54` | likely (check phase 136 intent: these may be the intended seam that the instrumentation bypasses) | med | S | CF-12 (workspace), CF-11 (messenger) |
| T-08 | `ze_core.conversation.retry.eligibility_payload`; `ZeApiSettings.capabilities_path`, `routing_config`, `memory_insights_config`; `ze_api.errors.CapabilityConfigError` | `ze_core/conversation/retry.py:234`; `apps/ze-api/ze_api/settings.py:79,87,109`; `errors.py:15` | confirmed | low | S | CF-07 (core), CF-09 (api) |
| T-09 | `ze_news.registry.by_tag` | `plugins/ze-news/ze_news/registry.py:32` | confirmed | low | S | CF-11 |

### 1c. Registered tools no agent can call

`@tool` registration succeeds, but no agent's `tools` list names them and skills only narrow tools (114), so the model never sees them.

| ID | Finding | Evidence | Conf. | Risk | Effort | Floor |
|---|---|---|---|---|---|---|
| U-01 | 10 of 15 `render_*` tools are unreachable: `render_table`, `render_chart`, `render_metric`, `render_timeline`, `render_form`, `render_choice_group`, `render_consent`, `render_connect_account`, `render_review`, `render_connections`. Only `render_list`, `render_progress`, `render_confirm`, `render_card` appear in an agent list (goals, finance). Phase 118 ("agents render a real chart") is not reachable: no agent lists `render_chart`. | `core/kernel/ze-components/ze_components/tools.py:273-507`; `git grep '"render_chart"'` → 0 outside tools.py; companion tools `ze_personal/agents/companion/agent.py:127` | confirmed | med (product decision: give companion the render tools, or delete) | S–M | CF-02 |
| U-02 | `nli_check_entailment`, `nli_grounding` registered at import (`ze_api/container.py:129`), listed by no agent; docs (5-6 mentions) present them as shared tools | `core/contracts/ze-agents/ze_agents/nli_tools.py:9,26` | confirmed | low | S | CF-01 |

### 1d. TypeScript (knip)

| ID | Finding | Evidence | Conf. | Risk | Effort | Floor |
|---|---|---|---|---|---|---|
| W-01 | 15 unused files in the vendored chart kit (`packages/ze-ui/src/charts/`): `area-chart-loading.tsx`, `bar-chart-loading.tsx`, `bar-squares.tsx` (635 lines), `bar-y-axis.tsx`, `chart-center-typography.ts`, `chart-stat-flow.tsx`, `line-chart-loading.tsx`, `line-series-terminal-marker.tsx`, `pattern-preset.tsx`, `pie-center-shell.tsx`, `pie-center.tsx`, `projection-line-end-marker.tsx`, `projection-line.tsx`, `visx-pattern.tsx`, `y-axis-ticks.ts`. Plus ~45 unused exports, 24 duplicate `X` + `default` exports, deps `@number-flow/react`, `@visx/gradient`, `@visx/pattern` unused. | knip "Unused files (21)", "Unused exports (72)", "Duplicate exports (24)", "Unused dependencies" | confirmed | low (check the chart kit's `index.tsx` public surface first) | M | CF-10 |
| W-02 | ze-web unused files: `entities/transaction/index.ts` (the doc example slice, never built), `features/switch-chat-session/index.ts`, `shared/effects/moving-border.tsx`, `shared/effects/text-generate-effect.tsx`; unused exports incl. `MessageBubble`/`TypingIndicator` re-exports, `mergeNavRoutes`, `formatTimestamp`, `retrieveWorkspaceFile`, `Sheet*`, `PageHeader`, `BackgroundBeams`, `ContextOverlay` index export; dep `@radix-ui/react-tooltip` unused | knip | confirmed | low | S | CF-10 |
| W-03 | ze-client: `@hey-api/client-fetch` declared but unused; `Client` and `WsActionFrame` exported types unused | knip | likely (codegen may need the dep at generate time: `scripts/codegen.ts:43` passes `--client @hey-api/client-fetch`) | low | S | CF-10 |
| W-04 | `scripts/codegen.ts` and `.opencode/plugins/graphify.js` reported unused — false positives (run by `make codegen` and OpenCode) | knip | — | — | — | — |

---

## 2. Config keys

### 2a. Keys in `apps/ze-api/config/config.yaml` that nothing reads

| ID | Key | Evidence | Conf. | Risk | Effort | Floor |
|---|---|---|---|---|---|---|
| K-01 | `workspace.output_preview_chars`, `workspace.storage_ceiling_bytes`, `workspace.run_lock_wait_seconds`, `workspace.follow_through_short_wait_seconds` | `config.yaml:323-326`; `ze_workspace/bootstrap.py:57-63` reads only `run_timeout_seconds`; the sidecar uses its own constants (`supervisor.py:17` `RUN_LOCK_WAIT_SECONDS`, `tools.py` `DEFAULT_SHORT_WAIT_SECONDS = 25.0`) | confirmed | low | S | CF-08 |
| K-02 | `skills.require_review`, `skills.reset.allow_full_dev_from_app` | `config.yaml:123-125`; `ze_skills/bootstrap.py:48,109` read only `match_threshold` and `recheck.*` | confirmed | low (review is always required in code) | S | CF-08 |
| K-03 | `contacts.follow_up.stale_days`, `contacts.follow_up.max_nudges` — the whole `follow_up` block is unread | `config.yaml:113-115`; no `"follow_up"` string read anywhere; `list_stale_for_follow_up(stale_days=...)` gets its value elsewhere | confirmed | low | S | CF-08 |
| K-04 | `dream.session_archive_threshold_days` | `config.yaml:301`; no reader | confirmed | low | S | CF-08 |
| K-05 | Generalize `apps/ze-api/tests/test_shipped_config_keys.py` (today it pins only `worldstate.*` and `correlation.*`, phase 170) into a check that every shipped leaf key has a reader, so dead keys cannot return. The scan used for this report was ~40 lines of Python (not committed). | `test_shipped_config_keys.py:1-50` | confirmed | low | S | CF-08 |

### 2b. Code reads keys the shipped YAML does not carry

These work through defaults. They are not bugs. They are undocumented knobs; either add them to `config.yaml` (commented) and `docs/configuration.md`, or drop the read and keep a constant.

| ID | Keys read (file:line) | Floor |
|---|---|---|
| K-06 | `finance.recurring_detection_enabled`, `recurring_detection_schedule`, `recurring_staleness_days`, `recurring_nudge_cooldown_days`, `recurring_price_change_threshold` (`ze_finance/plugin.py:44-57`) | CF-08 |
| K-07 | `prospecting.max_iterations`, `max_loop_tokens`, `browser_delay_ms`, `browser_max_text_chars`, `stale_timeout_minutes` (`ze_prospecting/plugin.py:32-42`) | CF-08 |
| K-08 | `messaging.automated_senders`, `inbound_poll_interval_seconds` (`ze_messenger/plugin.py:130,169`) | CF-08 |
| K-09 | `memory.consolidation.{unreviewed_ttl_days, contradicted_ttl_days, expiry_grace_days, episode_recency_days, episode_min_archive_batch, merge_silent_threshold, merge_llm_threshold, nightly_cron}` (`ze_memory/consolidator.py:103-262`, `bootstrap.py:145`); `memory.session_summary.{enabled, check_interval_minutes, min_episodes, max_transcript_tokens, session_inactivity_minutes}` (`bootstrap.py:153-161`, `session_summary.py:67-245`) | CF-08 |
| K-10 | `proactive.prune_cron`, `release_cron` (`ze_proactive/bootstrap.py:37,48`); `correlation.hypothesis_decay.*` (`ze_correlation/bootstrap.py:88`); `worldstate.stale_suspicion.window_days` (`ze_worldstate/bootstrap.py:127-129`) ⟳ 173 | CF-08 |

### 2c. Settings code paths for formats that no longer ship

| ID | Finding | Evidence | Conf. | Risk | Effort | Floor |
|---|---|---|---|---|---|---|
| K-11 | `ZeApiSettings.persona_config` falls back to a "Legacy: persona block embedded in config.yaml" and a hard-coded default profile; `active_profile()` has a "Legacy flat format" branch. `config/persona.yaml` ships, so both branches are dead. | `apps/ze-api/ze_api/settings.py:124-165` | confirmed | low | S | CF-09 |
| K-12 | `consolidation_config` docstring "Legacy YAML overrides" | `settings.py:93` | confirmed | low | S | CF-09 |

All 27 keys in `apps/ze-api/.env.example` have a reader.

---

## 3. Pre-v1 shim residue

`specs/arch/pre-v1-hard-cuts.md` forbids deprecated aliases, re-exports kept "for now", second vocabularies and compatibility wrappers.

| ID | Finding | Evidence | Conf. | Risk | Effort | Floor |
|---|---|---|---|---|---|---|
| S-01 | **E5 `encode()` "compat shim"** treats every input as a passage. 10 callers use it, including two that embed **queries**: `MemoryRetriever` (`retriever.py:148 query_emb = embedder.encode(query)`) and `fetch_context` (`ze_core/orchestration/nodes/context.py:219`, which feeds routing context and the open-query detector). E5 is asymmetric (`query:`/`passage:`), so retrieval scores are computed passage-vs-passage. **Coupling:** the open-query detector's 0.88 threshold was calibrated on this passage path. Switching the turn embedding to `encode_query` drops "what is still on my plate?" from 0.93 to 0.88 and makes the held-out row `oq-hold-en-pos-01` ("What's still on my plate this week?") fail (0.86). Removing the shim needs a recalibration (`make calibrate-open-query`, retrieval relevance floor). | `core/engine/ze-core/ze_core/embeddings.py:23,60-69`; callers in `ze_memory/{retriever,consolidator,session_summary,procedures/store}.py`, `ze_worldstate/matching.py:74-78`, `ze_correlation/push.py:50-52`, `ze_core/.../context.py:219`; detector `ze_priority/open_query.py:101-104`; scores measured this session with the local E5 model | confirmed (shim); likely (retrieval quality impact — measure) | high (relevance + calibration) | M | CF-02 (needs a short spec; ⟳ 173 for `matching.py`) |
| S-02 | `ZeError = ZeCoreError` alias: two names for the base error, 24 vs 29 source uses | `core/contracts/ze-agents/ze_agents/errors.py:5-6` | confirmed | low (mechanical) | M (touches ~50 files repo-wide) | CF-15 (runs last, alone) |
| S-03 | Re-export shims: `ze_worldstate/decay.py:5` re-exports `CONFIDENCE_FLOOR, DecayProfile, decay` from `ze_agents.claims` (only `cascade_from_evidence` is imported from it, `ze_api/container.py:495`); `ze_memory/types.py:11` re-exports `RetrievalRequest` (one importer, `ze_memory/policies.py:39`); `ze_onboarding/coordinator.py:6` re-exports `OnboardingError` (two in-package importers) | file:line given | confirmed | low | S | CF-14 ⟳ 173 (decay), CF-03 (memory), CF-01 (onboarding) |
| S-04 | `ze_core/db.py` and `ze_agents/db.py` both define the `DBPool` alias ("Database type aliases — agents annotate against DBPool") | `ze_core/db.py:1`, `ze_agents/db.py:1`; `ze_core/__init__.py:16`, `container.py:337` import the ze-core copy | confirmed | low | S | CF-07 |
| S-05 | `ze_api/api/routes/__init__.py` re-exports 20 route modules; `app.py` imports them directly; the list is already incomplete (no `collisions`, `notifications`, `loops`, `priority`, `procedures`, `skills`, `channels`) | `apps/ze-api/ze_api/api/routes/__init__.py:1-45` | confirmed | low | S | CF-09 |
| S-06 | `ze_personal/persona/identity.py:96` "legacy UserProfile object" branch — `UserProfile` no longer exists anywhere | `git grep -w UserProfile` → only this comment | confirmed | low | S | CF-04 |
| S-07 | `ze_skills/matching.py:122-179` keeps a `legacy` match list used when System One is off, uncalibrated or fails. It is the documented fallback (166), not a shim. Rename the variable (`e5_matches`) so it stops reading like residue. | file:line | confirmed | low | S | CF-14 |
| S-08 | Five per-package Alembic CLIs (`ze_core/migrate.py`, `ze_memory/migrate.py`, `ze_correlation/migrate.py`, `ze_proactive/migrate.py`, `ze_onboarding/migrate.py`) duplicate the meta-runner (`_resolve_url`, `current`, `history`, `_config`). Running one chain alone ignores cross-chain `depends_on` and the shared `alembic_version` table. Nothing calls them; `ze-core/pyproject.toml:25` still advertises `python -m ze_core.migrate`. | `git ls-files '*migrate.py'`; duplicate-helper scan | confirmed | low | S | CF-08 |
| S-09 | Legacy ze-core tables `user_facts`, `episodes`, `user_profile` are still created by `001_initial_schema` and never dropped. No code writes them. Only the contacts consolidator reads `episodes` (§7, R-06). AGENTS.md still lists them under ze-core. | `core/engine/ze-core/ze_core/migrations/versions/001_initial_schema.py:25-125`; `git grep -lw user_facts -- '*.py' ':!*/migrations/*'` → 0 | confirmed | med (migration; dev DBs wiped pre-v1) | M | CF-04 |

---

## 4. Dependency rules

Declared vs. actual imports, non-test source only (AST scan of every package; script not committed).

| ID | Finding | Evidence | Conf. | Risk | Effort | Floor |
|---|---|---|---|---|---|---|
| D-01 | **`ze-agents ↔ ze-onboarding` cycle can break today.** `ze-agents` imports `ze_onboarding` only in the dead `ze_agents/onboarding/` re-export package (X-07). Delete it and drop `ze-onboarding` from `ze-agents/pyproject.toml`. `ze_plugin/plugin.py:17` imports `OnboardingProvider` under `TYPE_CHECKING` only. | `core/contracts/ze-agents/ze_agents/onboarding/*`; `ze_onboarding` imports `ze_agents.errors/claims` (`coordinator.py:6`, `persistence.py:6`, `reset.py:6`) | confirmed | low | S | CF-01 |
| D-02 | **`ze-personal ↔ ze-news` cycle can break.** `ze-news → ze-personal`: `ze_news/agents/agent.py:18` imports `hold_token_sink, publish_honest_reply` from `ze_personal.agents.companion.honesty`; calendar, reminders and messenger agents import the same helper (5 importers). These are generic reply-honesty helpers; move them to `ze-agents` and re-export via `ze_sdk`. `ze-personal → ze-news`: `jobs/briefing.py:12-13` (`NewsPreferenceBuilder`, `GoalTitleProvider`, `PersonalizationSettings`) and `plugin.py:228`. After the move, `ze-news` no longer needs `ze-personal`, and `ze-calendar`, `ze-messenger` may drop it too if nothing else binds them. | file:line given | confirmed | med | M | CF-05 |
| D-03 | **`ze-automation` imports the engine.** `ze_automation/bootstrap.py:233-234` lazily imports `ze_core.conversation.make_graph_input` and `ze_core.telemetry.context.set_flow_context` inside `_workflow_executor`. `ze-automation` does not declare `ze-core`; the dependency graph forbids core-domain packages from reaching into the engine. Fix: `ze-api` passes the executor callable in (it already builds the workflow graph, `ze_api/workflow_graph.py`). ⟳ 181 (workflow runner) | file:line | confirmed | med | S | CF-05 ⟳ 181 |
| D-04 | **Core packages import the plugin SDK.** `ze-automation` (20 imports, e.g. `goals/planner.py:12`, `postgres.py:6`), `ze-worldstate` (`store.py:9`, `jobs/*`), `ze-skills` (`store.py:8`), `ze-priority` (`store.py:8`) import `ze_sdk`. `ze-sdk` declares `ze-automation`, so `ze-automation ↔ ze-sdk` is a real cycle. Core packages must import the owning package (`ze_agents`, `ze_proactive`, `ze_plugin`), never `ze_sdk`. | AST import scan | confirmed | low | M | CF-05 |
| D-05 | **Plugins bypass `ze_sdk` for most core packages.** Direct imports of `ze_agents` (ze-personal 39, calendar 20, news 16, finance 14, messenger 14, prospecting 9), `ze_logging` (~46), `ze_proactive` (14), `ze_communication` (messenger 9), `ze_data` (calendar, personal, prospecting), `ze_automation` (calendar 2), `ze_correlation` (personal 2). AGENTS.md: "Plugin code imports from `ze_sdk.*`". The boundary test (`test_plugin_boundaries.py:7`) forbids only `ze_core`, `ze_api`, `ze_plugin`, `ze_memory`. **Decide the rule first:** either (a) plugins may import `ze_logging` and `ze_agents` directly and AGENTS.md says so, or (b) a codemod moves all ~200 imports to `ze_sdk.*` and the test forbids every core root except `ze_sdk`. | AST import scan | confirmed | low (mechanical) | L (codemod over every plugin file) | CF-15 (runs last, alone) |
| D-06 | Undeclared deps (import without `pyproject.toml` entry): `ze-api` → `ze-agents`, `ze-communication`, `ze-plugin`, `ze-proactive`; `ze-automation` → `ze-plugin`; `ze-memory` → `ze-proactive` (`bootstrap.py:10`, `push_kinds.py:3`, `dream/job.py:14`); `ze-components` → `ze-logging`; `ze-google` → `ze-agents`; `ze-browser` → `ze-agents`; `ze-ingestion` → `ze-plugin`; `ze-onboarding` → `ze-plugin`; `ze-skills` → `ze-plugin`; `ze-priority` → `ze-logging`; `ze-plugin` → `ze-communication` (`webhook.py:6`), `ze-memory` and `ze-onboarding` (TYPE_CHECKING) | AST import scan | confirmed | low | S | CF-05 |
| D-07 | Declared but unused: `ze-browser` → `ze-core` (code imports only `ze_agents`); `ze-seed` → `ze-automation`, `ze-memory`, `ze-onboarding`; `ze-skills` → `ze-data`; `ze-workspace` → `ze-data`; `ze-worldstate` → `ze-components`; `ze-priority` → `ze-proactive` (it imports `ze_sdk.proactive` instead, D-04). `ze-api` → calendar/finance/news/prospecting/yt are entry-point installs, not dead. | AST import scan | confirmed | low | S | CF-05 |
| D-08 | `ze-plugin ↔ ze-memory` type-only cycle: `ze_plugin/signals.py:13` imports `ze_memory.types.Signal` under `TYPE_CHECKING`; `ze-memory` declares `ze-plugin`. Move `Signal` to `ze-plugin` (it is the contract) or type the protocol structurally. | file:line | confirmed | low | S | CF-05 |
| D-09 | AGENTS.md "Package dependency graph" is stale: says "No known drift from the import rules", says `ze-yt` imports `ze_logging` undeclared (now declared), and omits every edge above. | `AGENTS.md` dependency block | confirmed | low | S | CF-16 |

---

## 5. Stale docs and Makefile

False positives removed: phase-table history rows, model IDs (`intfloat/...`), the `docs/frontend.md` walk-through examples, branch-name patterns, gitignored paths.

| ID | Finding | Evidence | Conf. | Risk | Effort | Floor |
|---|---|---|---|---|---|---|
| M-01 | **`make migrate` ignores `DATABASE_URL_SYNC`.** `ZE_MIGRATE := cd $(ZE) && DATABASE_URL_SYNC=$(DB_SYNC_URL) ...` with `DB_SYNC_URL ?= postgresql+psycopg2://ze:ze@localhost:5432/ze`. The recipe overwrites any shell or floor `DATABASE_URL_SYNC`, so every floor's `make migrate*` hits the shared dev DB `ze`. Fix: `DB_SYNC_URL ?= $(or $(DATABASE_URL_SYNC),postgresql+psycopg2://ze:ze@localhost:5432/ze)` and document it. | `Makefile:10-11` | confirmed | med (safety) | S | CF-08 |
| M-02 | `make help` says `dev-eval` starts "without background jobs"; the target only sets `EVAL_MODE=true PUBLIC_URL=` (AGENTS.md is right: jobs still start) | `Makefile` help vs `dev-eval:` recipe | confirmed | low | S | CF-08 |
| M-03 | `test-seed` target missing from `make help` | Makefile scan | confirmed | low | S | CF-08 |
| M-04 | Docs name missing make targets: `make generate-components` (`core/kernel/ze-components/README.md:13,47`), `make test-data` (`core/kernel/ze-data/README.md:61`) | Makefile has neither | confirmed | low | S | CF-16 |
| M-05 | Renamed/removed symbols in package READMEs: `WorkflowAgent` → `WorkflowManagerAgent` (`ze-automation/README.md:16,22,31`); `AgentRegistry` (`ze-agents/README.md:26`, `docs/package-architecture.md:71`, `docs/sdk.md:32,263`); `ComponentRenderer` (`ze-components/README.md:17`); `TransactionExtractor` (`ze-ingestion/README.md:9`, `docs/features.md:111,122`); `EmailPlugin` (`ze-google/README.md:17`); `get_recent_transactions`, `get_account_balances` (`ze-finance/README.md:35`) | doc reference scan; each name has zero code hits | confirmed | low | S | owning package floor (CF-04/11/12) or CF-16 |
| M-06 | `docs/architecture.md`: `ze_agents/channels/` (moved to `ze_communication` in phase 83; lines 738-754), `ze_components/builders.py` (720, 728), `ChatContentImage` (686), `workflow_plans` (952) | doc reference scan | confirmed | low | S | CF-16 |
| M-07 | `docs/package-architecture.md`: `RoutingFallback` (161), `PostgresGoalSuggestionStore` (279), `agents/news/` (406), `personalization.py` (411), `browse_url` (447), `logging.py` (85) | doc reference scan | confirmed | low | S | CF-16 |
| M-08 | `docs/sdk.md`: `list_threads` (437), `BriefingJob` (466); `docs/scheduled-jobs.md:112` `synthesise_profile()`; `docs/memory.md:511` `expires_before` | doc reference scan | confirmed | low | S | CF-16 |
| M-09 | `sidecar/browser/README.md:138-148` names pre-monorepo paths `ze/browser/client.py`, `ze/tools/browser.py`, `ze/agents/prospecting/` | doc reference scan | confirmed | low | S | CF-12 |
| M-10 | Docs describe `Container.invoke_raw` (14 mentions) and the unreachable NLI tools as live (X-01, U-02) | grep | confirmed | low | S | with X-01/U-02 |
| M-11 | AGENTS.md migration table lists dead tables (`user_facts`, `episodes`, `user_profile`) as ze-core-owned (S-09); repository tree comment says `ze_agents/onboarding/  # Re-exports ze_onboarding types for agents` (X-07) | AGENTS.md | confirmed | low | S | CF-16 |
| M-12 | Docs still describe `explicit_hold` (`docs/configuration.md:430,508`, `docs/system-one.md:96,121`, `core/cognition/ze-worldstate/README.md:15`, AGENTS 168 row). On `main` the bar is live (`loop_judge.py:76-154`, `config.yaml:51`), so the docs are correct today. Floor 173 is expected to change the loop gate. ⟳ 173 | file:line | likely stale after 173 | low | S | CF-14 ⟳ 173 |

---

## 6. Organization

| ID | Finding | Evidence | Conf. | Risk | Effort | Floor |
|---|---|---|---|---|---|---|
| O-01 | **System One judge helpers duplicated across five modules:** `_bar` (5×), `_valid_noul` (4×), `_valid_choice` (3×), `build_state` (4×), `decide` (6×) in `ze_skills/judge.py`, `ze_memory/speech_act_judge.py`, `ze_worldstate/loop_judge.py`, `ze_worldstate/corroboration_judge.py`, `ze_core/judge.py`. Extract bar parsing and answer validation into `ze_agents/system_one.py` (the Protocol's home); keep each surface's `decide()` local. ⟳ 173 (loop_judge) ⟳ 182 (ze_core/judge) | duplicate-helper AST scan | confirmed | med | M | CF-14 ⟳ 173 ⟳ 182 |
| O-02 | **14 ze-core test files test other packages** (left behind by the phase 48/64 splits): `tests/memory/test_{consolidator,extractor,store}.py` → ze-memory; `tests/orchestration/test_{base_agent,delegate,registry,tool}.py`, `tests/progress/*`, `tests/interface/test_validation.py`, `tests/routing/test_calibration_{dataset,script}.py` → ze-agents; `tests/channels/test_{channels,registry}.py` → ze-communication | test-import scan: no import of `ze_core` in these files | confirmed | low | M | CF-01 (ze-agents), CF-03 (ze-memory), CF-05 (communication) |
| O-03 | ze-memory has 5 copies of `_to_list` (`consolidation_store.py:14`, `policies.py:62`, `retrieval_rerank.py:48`, `retriever.py:113`, `session_summary.py:31`); `_cosine` 3× (`ze_priority/tools.py:32`, `ze_finance/recurring/detector.py:71`, `ze_news/store.py:488`); `_parse_dt` 3× | duplicate-helper scan | confirmed | low | S | CF-03 (memory); others with their package |
| O-04 | Oversized modules worth splitting: `ze_api/api/schemas.py` 1,698 lines / 180 classes (§8); `ze_memory/retriever.py` 1,541; `ze_automation/goals/postgres.py` 1,104; `ze_memory/procedures/store.py` 1,040; `ze_api/container.py` 972 (`build_container` alone is ~550 lines, 425-972); `ze_automation/goals/executor.py` 933; `ze_memory/policies.py` 922; `ze_agents/base_agent.py` 906 | `wc -l` | confirmed | med | L each | schemas/container: CF-09; others: future floors |
| O-05 | **ze-web FSD boundaries are not enforced:** `.eslintrc.cjs` sets `"boundaries/element-types": "off"`. 6 upward imports: `entities/message/ui/MessageBubble.tsx` → `@/features/trace-state` and `@/widgets/message-trace`; `entities/primitive-tree/api/use{PluginScreen,PrimitiveRenderer}Actions.ts` → `@/features/send-context-notice`; `shared/lib/query-keys.ts` → `@/entities/ui-manifest`; `shared/ui/layout/TopBar.tsx` → `@/widgets/notification-bell` (⟳ 181). 31 same-layer cross-slice imports, e.g. 5 procedure hooks import `@/entities/workspace/api/workspaceFetch` (internal path of another entity); 11 `widgets/trace-panel` files deep-import `@/widgets/message-trace/ui/*`. | FSD scan; `apps/ze-web/.eslintrc.cjs` | confirmed | med | M | CF-10 ⟳ 181 |
| O-06 | ze-web bypasses the generated SDK: the procedures entity (5 hooks) and the workspace entity call `workspaceFetch`/raw `fetch` against `/api/v0/procedures*` and `/api/v0/workspace*`, so route renames break them silently | `entities/procedure/api/*.ts`, `entities/workspace/api/*.ts` | confirmed | med | M | CF-06 |
| O-07 | `ze_api/testing.py` is a production module that imports `tests.support.agent_modules`; only tests use `make_gate` | `apps/ze-api/ze_api/testing.py:1-20` | confirmed | low | S | CF-09 |
| O-08 | Domain code in `ze_api` root: `feedback_domain.py` (DataDomain for `feedback_records`, owned by ze-memory `zm024`), `interruption_domain.py` (DataDomain for `interruption_settings`, owned by ze-proactive `zpro004`), `push_kinds.WORKSPACE_RUN_COMPLETED` (workspace kind; ze-memory and ze-correlation already own their push kinds). See §8.2. | file:line | confirmed | low | S | CF-09 |
| O-09 | Inline SQL in routes: `api/routes/activity.py` (2 statements), `api/routes/memory.py` (4). Every other route delegates to a package `rest.py` or store. | grep `SELECT\|conn.fetch` | confirmed | low | S | CF-09 |

---

## 7. Known residue from the brief

| ID | Item | Verdict on `d70b7af7` | Evidence | Conf. | Risk | Effort | Floor |
|---|---|---|---|---|---|---|---|
| R-01 | `loop_judge` "conversation" state row | Live on `main`: `admission.py:64` calls `self._judge(prompt, CONVERSATION)`; the row sets the state key `user` and the 1,000-char cap. It becomes residue only if 173 moves the conversation gate. ⟳ 173 | `ze_worldstate/loop_judge.py:23-26,53-70` | likely (after 173) | low | S | CF-14 ⟳ 173 |
| R-02 | 173 trace shows a single `link_kind` | Not on `main` (`git grep link_kind` → 0). Recheck on the 173 branch after it lands. ⟳ 173 | — | — | — | S | CF-14 ⟳ 173 |
| R-03 | EN "what is still on my plate?" not caught by the open-query detector | **Not reproduced at the detector.** On the production path (`fetch_context` uses `embedder.encode` = passage) it scores 0.932 ≥ 0.88; "What's still on my plate this week?" 0.904. It fails only with `encode_query` (0.882 / 0.862). If the miss was seen live, look downstream: routing to the loops agent, `turn_surfacer` wiring, or a prompt with extra words. Tie-in: S-01 removal will flip this. | measured with local E5; `ze_priority/open_query.py:21` | confirmed (not reproducible) | — | S | CF-02 |
| R-04 | `make migrate` ignores `DATABASE_URL_SYNC` | **Confirmed** — M-01 | `Makefile:10-11` | confirmed | med | S | CF-08 |
| R-05 | Docs still mention `explicit_hold` | Correct on `main`; stale only once 173 lands — M-12 ⟳ 173 | — | likely | low | S | CF-14 |
| R-06 | **Contacts consolidator reads legacy `episodes` columns** | **Confirmed and worse: the job is inert.** `ContactsConsolidator._load_unprocessed` reads `FROM episodes WHERE contacts_extracted = false AND is_archive = false` and marks rows in `episodes`. Nothing inserts into `episodes` any more (`git grep "INSERT INTO episodes"` → 0); turns go to `memory_episodes`. So nightly contact extraction from conversation finds nothing. Fix: read `memory_episodes` with a ze-personal-owned watermark (new `zc` migration), drop `zc013`'s column and the legacy tables (S-09). | `plugins/ze-personal/ze_personal/contacts/consolidator.py:135-145,284`; `zc013_contacts_extracted_col.py` | confirmed | high (behavior: contacts start extracting again) | M | CF-04 |
| R-07 | `update_event` fields unreachable because `llm_schema` skips `str \| None` | **Confirmed and wider.** `Tool.llm_schema()` keeps only params whose annotation is exactly `str/int/float/bool/list/dict` (`ze_agents/tool.py:14,57-61`); `X \| None` and `list[str]` vanish from the schema. LLM-facing params the model never sees: `update_event.summary/start/end/description`; `send_email.thread_id` (thread-aware send, phase 85); `world_time.locations` (required `list[str]` — the tool cannot be called correctly); `get_positions/get_spending_summary/get_transactions.account_id/since/until`; `get_recurring_expenses.status`; `search_news.tags`, `get_headlines.tags`; `add_prospect.company/role`; `nli_grounding.evidence`. Injected params (`ctx`, `session_id`, `user_message_id`, stores, `restore_*` undo args) are hidden on purpose and must stay hidden — the fix needs an explicit "injected" marker rather than "hide anything non-primitive". | AST scan of `@tool` signatures; `plugins/ze-calendar/ze_calendar/agents/calendar/tools.py:113-121`, `ze_messenger/agents/messenger/tools.py:118`, `ze_calendar/timezone/tools.py:12`, `ze_finance/agents/finance/tools.py:98-224`, `ze_news/agents/tools.py:14,43`, `ze_prospecting/agents/tools.py:30` | confirmed | high (tool behavior changes; eval scenarios needed) | M | CF-01 |

---

## 8. ze-api: routes and structure

### 8.1 Route inventory

112 REST operations + `/ws` + docs mounts. Caller sources: generated SDK function used in `apps/ze-web/src` or `packages/ze-ui/src` (excluding tests), raw `fetch` paths, plugin `page_operation_id`/`settings_operation_id` (manifest-driven), `eval/`, `core/ops/ze-eval`, `scripts/`, Makefile. Plugin `rest_routes()` are listed with their plugin. "OpenAPI" checks AGENTS.md rules: `response_model`, `summary`, `description`, explicit camelCase `operation_id`, `/api/v0/` prefix.

**Callers found (keep).** All have `summary`, `description` and an `operation_id`.

| Area | Operations (method path → operationId) | Caller |
|---|---|---|
| activity | GET `/activity/heatmap` → getActivityHeatmap | web `entities/activity` |
| costs | GET `/costs/summary` → getCostSummary; GET `/costs/anomalies` → getCostAnomalies | web `entities/cost-entry` |
| data | GET `/data/domains`, GET `/data/export`, POST `/data/import`, POST `/data/delete-intent`, DELETE `/data` | web `entities/data-domain`, `features/{export,import,delete}-user-data` |
| goals | GET `/goals`, GET `/goals/{id}`, GET `/goals/{id}/traces`, POST `/goals/{id}/start`, POST `/goals/{id}/learnings/{lid}/review` | web `entities/goal` |
| health | GET `/health` → healthCheck | web `features/test-api-connection`, ze-client `blob.ts`, Makefile, `scripts/check_browser_health.py` |
| loops | GET `/loops`; POST `/loops/{id}/{confirm,close,drop}` | web `entities/loop` |
| memory | GET `/memory/feed`, `/memory/activity`, `/memory/timeline-bounds`, `/memory/graph`, `/memory/graph/entity/{id}`; POST `/memory/facts/review` | web `entities/memory-*` |
| messages | GET `/messages`, `/messages/traces`, `/messages/{id}/trace`, `/messages/feedback`; PUT `/messages/{id}/feedback` | web `features/load-chat-history`, `features/trace-state`, `entities/message*`; `eval/scenarios/memory.yaml:143` |
| notifications ⟳ 181 | GET `/notifications`, `/notifications/unread-count`, `/notifications/quiet-hours`; PUT `/notifications/quiet-hours`; POST `/notifications/read-all`, `/notifications/{id}/read` | web `entities/notification`, `entities/quiet-hours` |
| priority | GET `/priority/snapshot`; POST `/priority/override`, `/priority/override/{id}/unpin` | web `entities/priority-item` |
| procedures | GET `/procedures/candidates`, `/procedures/library`, `/procedures/{id}`; POST `/procedures/candidates/{id}/review`, `/procedures/{id}/disable`, `/procedures/{id}/edit` | web `entities/procedure` (raw fetch, O-06) |
| sessions | GET `/sessions`, `/sessions/search` | web `entities/session` |
| skills | GET `/skills`; POST `/skills/import`, `/{id}/approve`, `/{id}/approve-executables`, `/{id}/reject`, `/{id}/disable`, `/{id}/enable`; DELETE `/skills/{id}` | web `entities/skill`; `eval/calibration/skills.py`, Makefile |
| ui | GET `/ui/manifest` → getUiManifest | web `entities/ui-manifest` |
| workflows | GET `/workflows`, `/{id}`, `/{id}/executions`, `/{id}/executions/{eid}`, `/{id}/revisions`; POST `/{id}/trigger`, `/{id}/executions/{eid}/cancel` | web `entities/workflow` ⟳ 181 (runner) |
| workspace | GET `/workspace`, `/workspace/files`, `/workspace/files/{path}`, `/workspace/runs/{id}/events`, `/workspace/runs`; POST `/workspace/files`, `/workspace/runs/{id}/cancel` | web `entities/workspace` (raw fetch, O-06) |
| plugin pages | GET `/contacts/page`, `/news/page`, `/reminders/page`, `/news/settings` | manifest-driven: `page_operation_id` / `settings_operation_id` in `ze_personal/plugin.py:259`, `ze_news/plugin.py:152,161`, `ze_calendar/plugin.py:116` → `ze-client/src/plugin-ui.ts` |
| webhooks | POST `/webhooks/{source}` → receive_webhook | external (Gmail push); keep |
| eval | POST `/eval/chat` | `core/ops/ze-eval` (`client.py:22`, `runner.py:46`, `server.py:49`), `eval/calibration/companion_research_check.py:125` |

**No caller found (decide: delete, gate or wire).** Recommendation in the last column.

| ID | Operation | File | Note | Recommendation |
|---|---|---|---|---|
| A-01 | GET `/capabilities` → listCapabilities; PUT `/capabilities/{agent}/{intent}` → updateCapability | `routes/capabilities.py:18,37` | Capabilities are shown via the chat `/capabilities` command (`ChatWorkspace.tsx:160`). ⟳ 181 (capability/confirmation) | Delete unless 181 adds a settings UI |
| A-02 | GET `/channels` → `list_channels`; PATCH `/channels/{id}` → `update_channel` | `routes/channels.py:31,87` | Phase 85 surface; snake_case operation IDs break the camelCase convention; router carries its own `/api/v0` prefix | Keep only if a channels settings UI is planned; otherwise delete. Either way fix op IDs. |
| A-03 | GET `/collisions` → listCollisions | `routes/collisions.py:17` | Phase 126 query surface for collision observability | Keep as debug, gated by `EVAL_MODE`/dev, or delete |
| A-04 | GET `/contacts`, `/news`, `/reminders` (plugin list endpoints) | `ze_personal/api/routes.py:22`, `ze_news/api/routes.py:15`, `ze_calendar/api/routes.py:14` | Superseded by the server-driven `/…/page` endpoints | Delete |
| A-05 | GET `/costs/detail` → getCostDetail | `routes/costs.py:126` | — | Delete |
| A-06 | GET `/goals/{id}/learnings`, GET `/goals/{id}/learnings/{lid}`, POST `/goals/{id}/learnings/{lid}/promote` | `routes/goals.py:130,149,221` | Goal detail embeds learnings; no promote UI | Delete list/get; promote: wire into the learnings widget or delete |
| A-07 | POST `/ingest` → ingest | `routes/ingest.py:20` | No web, eval or script caller | Delete, or keep if an external share flow is planned (say so in docs) |
| A-08 | GET `/loops/{id}` → getLoop | `routes/loops.py:35` | `/loops` page uses the list | Delete or wire a detail view |
| A-09 | Memory: POST `/memory/consolidate`; GET `/memory/digest`, `/memory/facts`, `/memory/facts/quality`, `/memory/profile` | `routes/memory.py:118-249` | Memory feed and graph replaced these; consolidation runs on cron | Delete |
| A-10 | Dream (7): GET `/memory/dream/journal`, `/artifacts`, `/artifacts/{id}`; POST `/artifacts/{id}/{approve,reject,revise}`, `/runs/{id}/rollback` | `routes/dream.py:41-150` | Phase 78b review API; `config.yaml:315` "enable when React review page ships" — it never shipped | Product decision: build the review page or delete the routes (dream job keeps running) |
| A-11 | GET `/routing/log` → getRoutingLog | `routes/routing.py:10` | Debug audit | Gate behind dev/eval or delete |
| A-12 | POST `/sessions` → createSession | `routes/sessions.py:78` | Sessions are created by the WS turn | Delete |
| A-13 | GET `/skills/{id}`, `/skills/{id}/reference-files/{name}`; POST `/skills/{id}/refresh` | `routes/skills.py:43,63,215` | — | Delete, or wire refresh into skill management |
| A-14 | PATCH `/workflows/{id}/steps` → updateWorkflowSteps | `routes/workflows.py:153` | Steps change via the agent tool (revision audit 108 handles both actors) | Delete or wire an editor |
| A-15 | POST `/workspace/reset`; POST `/workspace/files/{path}/ingest` | `routes/workspace.py:137,296` | `reset` has no `response_model` | Delete or wire |
| A-16 | GET `/version` → getVersion; GET `/ws-schema` → getWsSchema | `routes/version.py:17`, `routes/ws_schema.py:12` | `version` is ops metadata (keep); `ws-schema` is unused — `scripts/codegen.ts` builds WS types from Python directly | Keep version; delete ws-schema |

**OpenAPI rule breaks.**

| ID | Finding | Evidence |
|---|---|---|
| A-17 | `/eval/chat` is outside `/api/v0`, has no `operation_id`, checks its own `x-ze-api-key` header instead of `require_api_key`, and is mounted in every mode (`app.py:126`); only `force_agent` checks eval mode | `routes/eval.py:26-60`. Mount it only when `settings.eval_mode`. |
| A-18 | snake_case operation IDs: `list_channels`, `update_channel`, `receive_webhook` | `routes/channels.py`, `routes/webhooks.py` |
| A-19 | No `response_model` (needs `response_class` + documented `responses`): GET `/data/export`, GET `/workspace/files/{path}`, POST `/workspace/reset`, GET `/workspace/runs/{id}/events` (NDJSON stream) | route table |
| A-20 | Mixed prefix style: `version`, `channels`, `ui`, `webhooks` routers carry their own prefix; `capabilities`, `memory`, `routing`, `workflows`, `costs` get a sub-path at `include_router` time; the rest get `/api/v0` only | `api/app.py:119-152` |
| A-21 | Plugin routes take two paths: runtime `mount_plugin_routers(app, container.plugins)` inside the lifespan (`app.py:75`, `plugin_routes.py`) and static import of `<pkg>.api.routes` for OpenAPI (`openapi_export.py:11-23`). A plugin whose `rest_routes()` differs from its `api/routes.py` would ship an SDK that does not match the server. | file:line |

**WebSocket.** No dead frame types. Every server→client type has a web handler; `ping`/`pong` is the live heartbeat (`ws-client.ts:131`, `endpoint.py:107`). Keep the protocol unchanged.

### 8.2 Target layout

Goal: a conventional FastAPI app. `ze-api` stays the composition root and owns no domain (AGENTS.md: "ze-api runs migrations but owns no tables"). Pre-v1 hard cut: no re-export aliases, no shims; the uvicorn target and `Makefile` change in the same floor.

```
apps/ze-api/ze_api/
├── main.py                    # create_app() + `app` (uvicorn ze_api.main:app)
├── lifespan.py                # migrate → assert schema → build container → dev seed → mount plugin routers
├── settings.py                # ZeApiSettings (legacy persona branches removed, K-11)
├── errors.py
├── cli/
│   ├── gmail_push.py          # was cli.py
│   ├── migrate.py             # was migrate.py (meta-runner; python -m ze_api.cli.migrate)
│   ├── seed.py                # was seed.py
│   └── openapi_export.py      # was openapi_export.py
├── wiring/                    # composition root: the only place that joins packages
│   ├── container.py           # ZeContainer + build_container, split by concern:
│   ├── stores.py              #   pools, stores
│   ├── agents.py              #   agent + plugin construction
│   ├── hooks.py               #   harness/memory/worldstate hooks
│   ├── jobs.py                # was compose.py
│   ├── workflow_graph.py      # unchanged role: joins ze_core + ze_personal
│   ├── webhooks.py            # was webhook.py (WebhookDispatcher)
│   ├── plugin_routes.py
│   ├── db.py
│   └── push_kinds.py          # CONFIRMATION_REQUEST / CONFIRMATION_TIMEOUT only
├── interface/native.py        # unchanged
└── api/
    ├── deps.py                # was api/dependencies.py, minus dead getters (X-25)
    ├── openapi.py             # tags + shared error responses
    ├── v0/
    │   ├── __init__.py        # router = APIRouter(prefix="/api/v0"); includes every domain router
    │   ├── activity/   {router.py, schemas.py}
    │   ├── costs/      {router.py, schemas.py}
    │   ├── data/       {router.py, schemas.py}
    │   ├── goals/      {router.py, schemas.py}
    │   ├── loops/      {router.py, schemas.py}
    │   ├── memory/     {router.py, schemas.py}        # graph, feed, activity, review
    │   ├── messages/   {router.py, schemas.py, views.py}  # messages.py + feedback.py + feedback_views.py
    │   ├── notifications/ {router.py, schemas.py}     # ⟳ 181
    │   ├── priority/   {router.py, schemas.py}
    │   ├── procedures/ {router.py, schemas.py}
    │   ├── sessions/   {router.py, schemas.py}
    │   ├── skills/     {router.py, schemas.py}
    │   ├── system/     {router.py, schemas.py}        # health, version, ui manifest
    │   ├── webhooks/   router.py
    │   ├── workflows/  {router.py, schemas.py}
    │   └── workspace/  {router.py, schemas.py}
    ├── shared_schemas.py      # ErrorDetail, pagination, cross-router types only
    ├── eval/router.py         # mounted only when settings.eval_mode (A-17)
    └── ws/                    # was api/websocket/ + api/ws.py; protocol unchanged
```

No services layer is needed: routes already delegate to package `rest.py` modules and stores, except the inline SQL in `activity.py` and `memory.py` (O-09), which moves to the owning package.

**File map** (every current file):

| Current | Destination |
|---|---|
| `api/app.py` | split: `main.py` (create_app, CORS, router includes) + `lifespan.py` |
| `api/dependencies.py` | `api/deps.py` (drop `get_openrouter_client`, `get_router`, `get_memory_store`, `get_graph`) |
| `api/openapi.py` | `api/openapi.py` |
| `api/schemas.py` (1,698 lines) | split into `api/v0/<domain>/schemas.py`; cross-router types → `api/shared_schemas.py`; WS frame models → `api/ws/schemas.py`; drop `ActorContextResponse` |
| `api/messages.py` | `api/v0/messages/router.py` |
| `api/routes/__init__.py` | delete (S-05) |
| `api/routes/{activity,costs,data,goals,loops,memory,notifications,priority,procedures,sessions,skills,workflows,workspace}.py` | `api/v0/<domain>/router.py` (minus routes the route-removal floor deletes) |
| `api/routes/feedback.py` | `api/v0/messages/router.py` |
| `api/routes/{health,version,ui}.py` | `api/v0/system/router.py` |
| `api/routes/webhooks.py` | `api/v0/webhooks/router.py` (op id → `receiveWebhook`) |
| `api/routes/eval.py` | `api/eval/router.py` (gated) |
| `api/routes/{capabilities,channels,collisions,dream,ingest,routing,ws_schema}.py` | per A-01…A-16 decision: delete, or `api/v0/<domain>/router.py` |
| `api/websocket/*` (10 modules) + `api/ws.py` | `api/ws/` (same modules; `ws.py` folds into `api/ws/__init__.py`) ⟳ 181 (`confirmation.py`) |
| `feedback_views.py` | `api/v0/messages/views.py` |
| `feedback_domain.py` | **out:** `core/cognition/ze-memory/ze_memory/feedback_records/data_domain.py` (ze-memory owns `feedback_records`; add `ze-data` dep) |
| `interruption_domain.py` | **out:** `core/contracts/ze-proactive/ze_proactive/data_domain.py` (ze-proactive owns `interruption_settings`; add `ze-data` dep) |
| `push_kinds.py` | `wiring/push_kinds.py` (confirmation kinds); `WORKSPACE_RUN_COMPLETED` **out** to `core/ops/ze-workspace/ze_workspace/push_kinds.py` |
| `container.py` (972) | `wiring/container.py` + `stores.py` / `agents.py` / `hooks.py` |
| `compose.py` | `wiring/jobs.py` |
| `workflow_graph.py`, `webhook.py`, `plugin_routes.py`, `db.py` | `wiring/` |
| `cli.py`, `migrate.py`, `seed.py`, `openapi_export.py` | `cli/` |
| `testing.py` | **out:** `apps/ze-api/tests/support/capability_gate.py` (O-07) |
| `settings.py`, `errors.py`, `interface/native.py` | unchanged paths (settings trimmed, K-11, X-25) |
| `migrations/` | unchanged |

### 8.3 Constraints for the floors

- Pre-v1 hard cut: no aliases from old module paths; update `Makefile` (`uvicorn ze_api.api.app:app` → `ze_api.main:app`, `python -m ze_api.migrate` → new path), `scripts/codegen.ts:34`, `docker-compose.yml`, and docs in the same floor.
- Any change to a path or `operation_id` regenerates `@myguyze/ze-client` (`make codegen`, `@hey-api/openapi-ts`) and updates ze-web in the same floor. The plugin `page_operation_id` strings (`getContactsPage`, `getNewsPage`, `getNewsSettings`, `getRemindersPage`) must keep matching.
- Keep the WS protocol unchanged (no dead frames found).
- ⟳ 181: `api/websocket/confirmation.py`, the notifications routes and the bell. Do not move or edit them until 181 lands; then rebase.

### 8.4 Floor split for ze-api

Two floors, in order: **CF-06** (route removal + op-id fixes + ze-client regen + ze-web call sites + SDK use for procedures/workspace) and then **CF-09** (restructure, file moves, schema split, domain move-outs). CF-06 changes only route functions and their schemas plus generated client and ze-web entities; CF-09 moves files after CF-06 lands, so the two never edit the same file at the same time.

---

## 9. Tooling

| ID | Finding | Proposal | Floor |
|---|---|---|---|
| G-01 | graphify phantom nodes (§0 item 7) make `explain`/`affected` unreliable for re-exported and commonly imported names | Add `scripts/graphify_reexports.py`: (1) AST-parse `packages/ze-sdk/ze_sdk/*.py` and every `__init__.py` for `from X import Y [as Z]` re-exports; (2) load `graphify-out/graph.json`; (3) for each sourceless node whose label matches a re-exported name (or a unique class/function name elsewhere), repoint its edges to the canonical node and drop the phantom; (4) write the graph back. The Maestro runs it right after `graphify update .` on the ground checkout. Until then: confirm with `git grep -w <name>` plus `git grep "<name>" packages/ze-sdk` before trusting a low in-degree. | CF-13 |
| G-02 | Boundary test is narrower than the rule (D-05) | Extend `test_plugin_boundaries.py` once the rule is settled; add a test that core packages never import `ze_sdk` (D-04) | CF-05 / CF-15 |
| G-03 | Vulture is not in the toolchain | Add `vulture` with a checked-in whitelist (`@tool`, `@agent`, `@render_tool`, `@mcp.tool`, FastAPI routes, Pydantic validators, ZePlugin hooks, Alembic `upgrade/downgrade`, pytest fixtures) as a `make deadcode` report target (not a gate) | CF-13 |

---

## 10. Notes on false positives

Do not delete these, even though tools flag them:

- FastAPI route functions, `@tool` functions, `@render_tool` functions, `@mcp.tool` functions (`ze_eval/server.py`), Pydantic `@field_validator` methods, sidecar endpoints.
- `@agent` classes (`FinanceAgent`, `CalendarAgent`, `ResearchAgent`, `WorkflowManagerAgent`): registered by decorator.
- `ze-api`'s declared deps on plugin packages: installed for entry-point discovery.
- Enum members and dataclass fields marked "likely" in §1: some values arrive from DB rows or model JSON. Check stored values before deleting.
- `scripts/codegen.ts`, `.opencode/plugins/graphify.js`: run by tools, not imported.

---

## 11. Ranked top 20

Ranked by value (correctness and safety first), then by risk-adjusted effort.

| Rank | ID | Finding | Why first | Effort | Floor |
|---|---|---|---|---|---|
| 1 | R-07 | `llm_schema` hides `X \| None` and `list[X]` params from the model (update_event, send_email thread_id, world_time locations, finance filters…) | Silent tool breakage in ~14 user-facing tools | M | CF-01 |
| 2 | R-06 | Contacts consolidator reads the dead `episodes` table: nightly contact extraction does nothing | A shipped feature is inert | M | CF-04 |
| 3 | M-01 | `make migrate` overrides `DATABASE_URL_SYNC` and hits the shared dev DB | Safety for every floor | S | CF-08 |
| 4 | S-01 | E5 `encode()` shim embeds queries as passages (retrieval, fetch_context) | Retrieval quality; needs recalibration | M | CF-02 |
| 5 | U-01 | 10 `render_*` tools (incl. `render_chart`) unreachable by any agent | Phase 118 feature not reachable | S–M | CF-02 |
| 6 | D-03 | `ze-automation` imports `ze_core` (engine) | Layering break, undeclared | S | CF-05 ⟳ 181 |
| 7 | D-04 | Core packages import `ze_sdk` (`ze-automation ↔ ze-sdk` cycle) | Real dependency cycle | M | CF-05 |
| 8 | D-01 / X-07 | Delete dead `ze_agents/onboarding/` → breaks the `ze-agents ↔ ze-onboarding` cycle | One-file fix removes a documented cycle | S | CF-01 |
| 9 | D-02 | Move reply-honesty helpers out of ze-personal → breaks `ze-personal ↔ ze-news` | Second documented cycle | M | CF-05 |
| 10 | A-01…A-16 | Remove ~35 routes with no caller (after per-route decision) | Smaller API, smaller SDK | M | CF-06 |
| 11 | A-17 | `/eval/chat` mounted in every mode with its own auth path | Attack surface in normal runs | S | CF-06 |
| 12 | S-09 | Drop legacy `user_facts`, `episodes`, `user_profile` tables | Dead schema; pairs with R-06 | S | CF-04 |
| 13 | T-01 | Goal-suggestion accept/dismiss path is test-only | Feature gap or dead code: decide | M | CF-04 |
| 14 | K-01…K-05 | 9 unread config keys + generalized shipped-keys test | Config honesty; stops recurrence | S | CF-08 |
| 15 | O-05 | Enable FSD boundary lint; fix 6 upward + 31 cross-slice imports | Architecture rule is unenforced | M | CF-10 ⟳ 181 |
| 16 | X-21 / X-22 | Delete Trading212 order-placement methods and finance risk stubs | Unused money-moving code | S | CF-11 |
| 17 | O-01 | Extract System One judge helpers (5 copies) | Duplication across the newest code | M | CF-14 ⟳ 173 ⟳ 182 |
| 18 | §8.2 | Restructure `ze_api` (main/lifespan/wiring/api.v0, schemas split, domain move-outs) | Conventional layout; ze-api owns no domain | L | CF-09 |
| 19 | G-01 | graphify re-export/phantom repair script | Makes `affected` trustworthy for every role | S | CF-13 |
| 20 | X-01…X-26 batch | Remove confirmed dead code in ze-agents, ze-memory, ze-core, ze-workspace | Low risk, clears noise | S each | CF-01/03/07/12 |

---

## 12. Proposed cleanup floors

Each floor fits one Sonnet lane. **No two floors edit the same file at the same time.** Floors that run in parallel own disjoint paths (the "Owns" column, with its exclusions). Where two scopes must touch one file, the order below serializes them: CF-02 after CF-03 (ze-memory `encode` call sites); CF-05 after CF-04 and CF-11 (`ze_automation/goals/*` and messenger import lines); CF-13 and CF-09 after CF-08 (Makefile); CF-09 after CF-05 and CF-06 (`pyproject.toml`, `api/schemas.py`); CF-14 after CF-01 and CF-03. Two further exceptions, also handled by ordering:

1. `AGENTS.md`, `docs/*.md` (except `docs/configuration.md`) and `specs/README.md` belong to **CF-16**, which lands last. Every other floor records the doc changes it needs in its floor Handoffs note; CF-16 applies them. Package `README.md` files belong to the floor that owns the package. This bends the "docs are part of done" rule, so the user should confirm it (alternative: each floor edits docs and floors land strictly in sequence).
2. Repo-wide renames (**CF-15**: `ZeCoreError` → `ZeError`, plugin imports via `ze_sdk`) touch files every other floor owns, so CF-15 runs alone after the others land.

Run CF-02, CF-05 (D-03 part), CF-06, CF-09, CF-10, CF-14 only after **181** and **173** land (and **182** for CF-14).

| Floor | Scope (rows) | Owns (paths) | Depends on | Size | Needs spec? |
|---|---|---|---|---|---|
| **CF-01 ze-agents contracts** | R-07 (tool schema + injected-param marker + eval scenario per affected tool), X-03, X-05, X-07/D-01, U-02, S-03 (onboarding re-export), item 1 residual, O-02 (ze-agents tests out of ze-core) | `core/contracts/ze-agents/**` except `system_one.py` (CF-14) and the new `honesty.py` (CF-05), `core/ops/ze-onboarding/ze_onboarding/{coordinator,__init__}.py`, `core/engine/ze-core/tests/{orchestration,progress,interface,routing/test_calibration_*}` → `core/contracts/ze-agents/tests/` | — | M | Small spec for R-07 (tool contract change) |
| **CF-02 embeddings + render tools** | S-01 (remove `encode` shim, explicit `encode_query`/`encode_passage`, recalibrate open-query and relevance floor), R-03, U-01 (wire render tools to companion or delete) | `ze_core/embeddings.py`, `ze_core/orchestration/nodes/context.py`, `ze_priority/open_query.py`, the 10 `encode` call sites, `ze_components/tools.py`, `ze_personal/agents/companion/agent.py`, `eval/calibration/open_query*` | 173 (worldstate `matching.py`) | M | Yes (calibration, behavior) |
| **CF-03 ze-memory dead code** | X-04, X-08–X-14, T-03, T-04, S-03 (`RetrievalRequest`), O-03 (`_to_list`), O-02 (memory tests out of ze-core) | `core/cognition/ze-memory/**` except `feedback_records/`, `migrate.py` (CF-08) and `speech_act_judge.py` (CF-14), `core/cognition/ze-correlation/ze_correlation/store.py`, `core/engine/ze-core/tests/memory/` | — | M | No |
| **CF-04 personal + automation residue** | R-06 (consolidator on `memory_episodes` + watermark migration), S-09 (drop legacy tables), T-01 (decide), T-02, X-15, X-24, T-06, S-06, X-23 (briefing) | `plugins/ze-personal/**` (except `agents/companion/honesty.py`, `agents/companion/agent.py`), `core/automation/ze-automation/ze_automation/goals/**`, one new `zc` migration numbered after 181 lands (181 takes `zc033`), `core/engine/ze-core/ze_core/migrations/versions/` (new file only) | — | M | Yes (R-06 migration, T-01 decision) |
| **CF-05 dependency hygiene** | D-02 (honesty helpers → ze-agents/ze_sdk), D-03 ⟳ 181, D-04, D-06, D-07, D-08, G-02 (core-must-not-import-ze_sdk test), O-02 (communication tests) | every `pyproject.toml`; `ze_automation/bootstrap.py`; import lines in `ze-automation`, `ze-worldstate`, `ze-skills`, `ze-priority` that use `ze_sdk`; `ze_personal/agents/companion/honesty.py` + its 5 importers; `ze_plugin/signals.py`; `core/engine/ze-core/tests/channels/` | 181 (D-03 part) | M | No (ADR note for D-02 placement) |
| **CF-06 ze-api route removal + client regen** | A-01–A-19 (per-route decisions from the user), O-06 (procedures/workspace onto the SDK) | `apps/ze-api/ze_api/api/routes/*.py` (route functions only), the matching classes in `api/schemas.py`, plugin `*/api/routes.py`, `packages/ze-client/src/generated/**`, `apps/ze-web/src/entities/{procedure,workspace,…}/api/**` | 181 | M | Route decisions only (user picks from §8.1) |
| **CF-07 ze-core dead code** | X-01, X-02, X-16, S-04, T-08 (core part) | `core/engine/ze-core/ze_core/**` except files owned by CF-02 / CF-14 | 182 | S | No |
| **CF-08 config + Makefile + migrate CLIs** | K-01–K-10, M-01–M-03, S-08 | `apps/ze-api/config/config.yaml`, `apps/ze-api/tests/test_shipped_config_keys.py`, `Makefile`, `docs/configuration.md`, the five package `migrate.py` files, `ze-core/pyproject.toml` comment | — | S | No |
| **CF-09 ze-api restructure** | §8.2 layout, X-25, K-11, K-12, S-05, O-04 (schemas, container), O-07, O-08, O-09, A-20, A-21 | `apps/ze-api/**` (all), `ze_memory/feedback_records/data_domain.py` (new), `ze_proactive/data_domain.py` (new), `ze_workspace/push_kinds.py` (new), `scripts/codegen.ts`, `docker-compose.yml` | CF-06, 181 | L | Short plan (file map is §8.2) |
| **CF-10 ze-web / ze-ui tidy** | W-01–W-03, O-05 (enable boundaries lint, fix imports) ⟳ 181 (TopBar/bell) | `apps/ze-web/**` except files CF-06 touched, `packages/ze-ui/**`, `apps/ze-web/.eslintrc.cjs` | CF-06, 181 | M | No |
| **CF-11 finance, messenger, google, news** | X-21, X-22, T-05, T-07 (messenger), T-09, X-23 (messenger), README fixes (M-05 finance/google) | `plugins/ze-finance/**`, `integrations/ze-trading212/**`, `integrations/ze-google/**`, `plugins/ze-messenger/**` (except honesty import line, CF-05), `plugins/ze-news/ze_news/registry.py` | — | S | No |
| **CF-12 workspace, proactive, data, eval, sidecar** | X-06, X-17, X-18, X-19, X-20, T-07 (workspace), item 6 hardening (task refs, lifespan), M-09 | `core/ops/ze-workspace/**` (except new `push_kinds.py`), `core/contracts/ze-proactive/ze_proactive/job.py`, `core/kernel/ze-data/**`, `core/ops/ze-eval/**`, `sidecar/**` | — | S | No |
| **CF-13 tooling** | G-01 (graphify repair script), G-03 (`make deadcode` + whitelist), item 4 note | `scripts/graphify_reexports.py`, `scripts/vulture_whitelist.py`, Makefile target block for `deadcode` (coordinate with CF-08: CF-13 lands after CF-08) | CF-08 | S | No |
| **CF-14 System One + loop residue** | O-01 (judge helper kit), S-07, S-03 (`decay.py`), R-01, R-02, M-12, X-26 | `ze_agents/system_one.py` (helpers only; coordinate with CF-01 by landing after it), `ze_skills/judge.py`, `ze_skills/matching.py`, `ze_memory/speech_act_judge.py`, `ze_worldstate/{loop_judge,corroboration_judge,decay}.py`, `ze_core/judge.py`, `ze_core/routing/judge.py`, `core/cognition/ze-worldstate/README.md` | 173, 182, CF-01 | M | No |
| **CF-15 repo-wide renames** | S-02 (`ZeCoreError` → `ZeError`), D-05 (plugin imports via `ze_sdk` codemod, after the user settles the rule) | any file; runs alone | all others | L | Rule decision for D-05 |
| **CF-16 docs sweep** | D-09, M-04–M-08, M-10, M-11 + doc deltas collected from every other floor's Handoffs note; coverage check against `git diff main...HEAD` | `AGENTS.md`, `docs/*.md` (except `configuration.md`), `README.md`, `specs/README.md`, package READMEs not owned above | all others | M | No |

### Suggested order

1. Now (no in-flight overlap, disjoint paths): **CF-08**, **CF-01**, **CF-03**, **CF-04**, **CF-11**, **CF-12** in parallel.
2. After CF-08: **CF-13**.
3. After 181 + 173 land: **CF-06**; **CF-05** (after CF-04, CF-11); **CF-02** (after CF-03).
4. After 182 lands: **CF-07**, then **CF-14** (after CF-01, CF-03).
5. After CF-05 and CF-06: **CF-09**; after CF-06: **CF-10**.
6. Last: **CF-15** (alone), then **CF-16**.

## Decisions the user needs to make

1. Per-route keep/delete for A-01 – A-16 (§8.1), especially the dream review API (A-10) and goal-suggestion acceptance (T-01).
2. Render tools (U-01): give companion the `render_*` tools, or delete the unreachable ones.
3. Plugin import rule (D-05): plugins import only `ze_sdk` (codemod), or `ze_agents`/`ze_logging` stay allowed and AGENTS.md says so.
4. Docs ownership (§12 exception 1): one docs floor at the end, or docs inside each floor with strictly sequential landing.

---

## Decisions (2026-10-16)

The user answered the four open questions above (relayed by the Maestro on 2026-10-16). This section records each decision and how it changes the floor table in §12. Where this section and an earlier section disagree, this section wins.

### D1. Routes (§8.1)

The user accepted the recommendations in §8.1, with these specifics:

| Rows | Decision | Floor change |
|---|---|---|
| A-01 capabilities (GET, PUT) | Delete (no settings UI planned). ⟳ 181: confirm 181 adds no caller before deleting. | CF-06 |
| A-02 channels (GET, PATCH) | Delete (no channels settings UI planned). The `list_channels`/`update_channel` op-ID fix in A-18 becomes moot. | CF-06 |
| A-03 collisions, A-11 routing log | **Gate** behind dev/eval: mount the routers only when `settings.eval_mode` (or a dev flag), the same mechanism as `/eval/chat` (A-17). | CF-06 adds one shared "dev/eval-only router" include in `app.py`; CF-09 keeps that split in `main.py` (`api/eval/` holds eval chat, collisions and routing log). |
| A-04 plugin list endpoints, A-05 cost detail, A-07 ingest, A-08 get loop, A-09 memory (5), A-12 create session, A-13 skill get/reference-files/refresh, A-15 workspace reset + file ingest, A-16 ws-schema | Delete. | CF-06 |
| A-06 goal learnings | Delete all three (list, get, **promote**). | CF-06 |
| A-10 dream review API | Delete all 7 routes **and** the config key `dream.review_notifications_enabled` (`config.yaml:315`) with its reader (`ze_memory/dream/job.py:172`), its tests (`tests/dream/test_dream_job.py:149,194`) and the `dream_review` push kind. Open point for CF-06's plan: with no review path, `needs_review` artifacts have no exit. Pick one in the plan: the dream pass stops producing `needs_review` (auto-promote or reject at the bar), or a sweep expires them. | CF-06 now edits `ze-memory/ze_memory/dream/{job,store,promoter}.py` for code the route removal orphans. CF-03 lands first (§12 order step 1), so the files are free. `config.yaml` stays with CF-08; CF-06 runs after CF-08 and removes only that one key. |
| A-14 PATCH workflow steps | Delete. ⟳ 181 (workflow runner). | CF-06 |
| A-16 `/version` | Keep. | — |
| A-17 – A-21 | Fix all: gate `/eval/chat`; camelCase op IDs (`receiveWebhook`); explicit `response_class` + `responses` for the 4 routes without `response_model`; one prefix style; one source of plugin routes for both runtime and OpenAPI. | A-17, A-18, A-19 → CF-06 (they change the SDK). A-20, A-21 → CF-09 (layout). |

**Orphans:** store, `rest.py` and schema code that only the deleted routes used is deleted in the same floor (CF-06), after `git grep` shows no other caller. Regenerate `@myguyze/ze-client` and update ze-web in the same floor.

### D2. Render tools (U-01)

Give the `render_*` tools to the companion agent (`ze_personal/agents/companion/agent.py:127`), with an eval scenario that asserts a chart request produces a `render_chart` component. No render tool is deleted.

Floor change: CF-02 owns this. Add the scenario to `eval/scenarios/companion.yaml` (CF-02 owns that file for this change). Check that the companion's system prompt says when to render, and that `render_*` calls stay READ-only so Retry eligibility (165/180) is unchanged.

### D3. Plugin imports (D-05)

Plugins import **only** through `ze_sdk.*`. CF-15 runs the codemod, adds any missing re-exports to `ze_sdk` (for example `ze_communication`, `ze_data.portability.assembler`, `ze_automation.workflow.scheduler`, `ze_correlation.types`, `ze_agents.claims`), and changes `packages/ze-sdk/tests/test_plugin_boundaries.py` so a plugin may import no `ze_*` root except `ze_sdk` and plugin packages it declares. AGENTS.md "Imports" already states the rule; CF-16 removes any wording that allows exceptions.

Floor change: CF-15 scope confirmed as L. CF-05 no longer decides the rule; it only fixes core-package edges (D-03, D-04, D-06 – D-08) and the two cycles.

### D4. Docs

One docs floor runs last (CF-16). Every other floor writes the doc changes it needs as an entry in its floor Handoffs note (`### <date> FROM <floor> TO CF-16: doc delta` + file, section, and the new text or the fact that changed). Package READMEs stay with the floor that owns the package. CF-16 applies the collected deltas, the stale rows in §5, and the AGENTS.md updates, then runs the coverage check against `git diff main...HEAD` over every landed cleanup floor.

Floor change: exception 1 in §12 is now the rule. `docs/configuration.md` stays with CF-08.

### Migration numbering

181 takes `zc033`. CF-04 numbers its ze-core migration (drop `user_facts`, `episodes`, `user_profile`) and its ze-personal watermark migration after 181 lands, using the next free `zc` revisions on `main` at that time.

---

## Floor briefs

One paragraph per floor, for the Maestro to paste into a floor's role prompt. "Gate" means what must be on `main` before the floor branches. Every floor: pre-v1 hard cut, re-verify each row on current `main` before deleting, `make test-<pkg>` per touched package and `make test-py` before review, doc deltas to the Handoffs note (D4), commit only when asked.

**CF-01 — ze-agents contracts.** Scope: R-07 (make `Tool.llm_schema()` emit `X | None` as optional typed params and `list[X]` as typed arrays; add an explicit marker for injected params so `ctx`, `session_id`, `user_message_id`, stores and `restore_*` undo args stay hidden; one eval scenario or unit test per affected tool: `update_event`, `send_email`, `world_time`, the finance filters, `search_news`/`get_headlines`, `add_prospect`), X-03, X-05, X-07/D-01 (delete `ze_agents/onboarding/`, drop `ze-onboarding` from `ze-agents` deps), U-02 (decide: list the NLI tools on an agent or delete them; default delete), S-03 (`OnboardingError` re-export), the `stream_complete_with_tools` temperature gap, and O-02 (move the ze-agents tests out of `ze-core/tests`). Owns: `core/contracts/ze-agents/**` except `system_one.py` and the new `honesty.py`; `ze_onboarding/{coordinator,__init__}.py`; the ze-core test dirs listed in §12. Depends: none. Gate: none. Migration: none. Needs a short spec for R-07, since every plugin tool's visible schema changes.

**CF-02 — embeddings and render tools.** Scope: S-01 (delete the `encode()` shim; every caller picks `encode_query` or `encode_passage`; recalibrate the open-query threshold with `make calibrate-open-query` and recheck the memory relevance floor), R-03 (re-measure "what is still on my plate?" after the change), and D2 (companion gets the `render_*` tools plus an eval scenario). Owns: `ze_core/embeddings.py`, `ze_core/orchestration/nodes/context.py`, `ze_priority/open_query.py`, the 10 `encode` call sites (ze-memory, `ze_worldstate/matching.py`, `ze_correlation/push.py`), `ze_components/tools.py`, `ze_personal/agents/companion/agent.py`, `eval/calibration/open_query*`, `eval/scenarios/companion.yaml`. Depends: CF-03 (shared ze-memory files). Gate: 173 (worldstate `matching.py`). Migration: none. Needs a spec (retrieval and calibration behavior change).

**CF-03 — ze-memory dead code.** Scope: X-04, X-08 – X-14, T-03, T-04, the `RetrievalRequest` re-export (S-03), the five `_to_list` copies (O-03), and the ze-memory tests that live in `ze-core/tests/memory` (O-02). Owns: `core/cognition/ze-memory/**` except `feedback_records/`, `migrate.py`, `speech_act_judge.py`; `ze_correlation/store.py`; `core/engine/ze-core/tests/memory/`. Depends: none. Gate: none. Migration: none. Check stored values before deleting the enum members marked "likely".

**CF-04 — personal and automation residue.** Scope: R-06 (the contacts consolidator reads `memory_episodes` and tracks progress with a ze-personal-owned watermark), S-09 (drop `user_facts`, `episodes`, `user_profile`, and the `zc013` column), T-01 (the user still has to choose: wire goal-suggestion accept/dismiss into a tool, or delete it with its tests; ask through the Maestro before building), T-02, X-15, X-24, T-06, S-06, and `BriefingJob._persons` (X-23). Owns: `plugins/ze-personal/**` except `agents/companion/{honesty,agent}.py`; `ze_automation/goals/**`; new migration files only. Depends: none. Gate: **181 must land first for the migration numbers** (181 takes `zc033`; use the next free `zc` revisions). Migration: one ze-core migration (drop legacy tables) and one ze-personal migration (watermark), each with a `depends_on` that orders it after the other chains it touches. Needs a short spec (R-06 behavior change; contacts start extracting again).

**CF-05 — dependency hygiene.** Scope: D-02 (move `hold_token_sink`/`publish_honest_reply` to a new `ze_agents/honesty.py`, re-export via `ze_sdk`, update the 5 importers; drop `ze-personal` from `ze-news` deps, and from `ze-calendar`/`ze-messenger` if nothing else binds them), D-03 (`ze-api` injects the workflow executor; `ze-automation` stops importing `ze_core`), D-04 (core packages stop importing `ze_sdk`), D-06, D-07, D-08 (move `Signal` or type it structurally), G-02 (a test that core packages never import `ze_sdk`), and the ze-communication tests in `ze-core/tests/channels` (O-02). Owns: every `pyproject.toml`; `ze_automation/bootstrap.py`; the `ze_sdk` import lines in ze-automation, ze-worldstate, ze-skills and ze-priority; `ze_personal/agents/companion/honesty.py` and its 5 importers; `ze_plugin/signals.py`; `core/engine/ze-core/tests/channels/`. Depends: CF-04, CF-11. Gate: 181 (workflow runner, D-03). Migration: none. Writes a short ADR note for where the honesty helpers live.

**CF-06 — ze-api route removal and client regeneration.** Scope: D1 in full (delete the routes listed, gate collisions and routing log with `/eval/chat` behind dev/eval, delete the dream review API with `dream.review_notifications_enabled`, its reader, its push kind and the orphaned store code, and settle what happens to `needs_review` artifacts), A-17 – A-19, O-06 (procedures and workspace entities call the generated SDK, not raw `fetch`), `make codegen`, ze-web call sites. Owns: `apps/ze-api/ze_api/api/routes/*.py` (route functions), the matching classes in `api/schemas.py`, `api/app.py` (router includes only), plugin `*/api/routes.py`, `packages/ze-client/src/generated/**`, the affected `apps/ze-web/src/entities/**/api/**`, `ze-memory/ze_memory/dream/{job,store,promoter}.py` (orphans only), the one `config.yaml` key. Depends: CF-03, CF-08. Gate: 181 (capabilities, notifications, bell, workflow runner). Migration: none. The plugin `page_operation_id` strings must keep matching.

**CF-07 — ze-core dead code.** Scope: X-01 (`Container.invoke_raw`), X-02, X-16, S-04 (one `DBPool` alias, in ze-agents), and the ze-core part of T-08. Owns: `core/engine/ze-core/ze_core/**` except `embeddings.py`, `orchestration/nodes/context.py` (CF-02), `judge.py` and `routing/judge.py` (CF-14). Depends: none. Gate: 182 (routing). Migration: none.

**CF-08 — config, Makefile, migrate CLIs.** Scope: K-01 – K-04 (delete the 9 unread keys), K-05 (turn `test_shipped_config_keys.py` into "every shipped leaf key has a reader"), K-06 – K-10 (add the code-only knobs to `config.yaml` as comments and to `docs/configuration.md`, or drop the read; pick per key), M-01 (`DB_SYNC_URL ?= $(or $(DATABASE_URL_SYNC),…)`), M-02, M-03, and S-08 (delete the five package `migrate.py` CLIs and the `ze-core/pyproject.toml` comment). Owns: `apps/ze-api/config/config.yaml`, `apps/ze-api/tests/test_shipped_config_keys.py`, `Makefile`, `docs/configuration.md`, the five `migrate.py` files. Depends: none. Gate: none. Migration: none. Land this first: it stops floors from migrating the shared DB `ze` by accident.

**CF-09 — ze-api restructure.** Scope: the §8.2 layout and file map (`main.py` + `lifespan.py`, `cli/`, `wiring/`, `api/v0/<domain>/{router,schemas}.py`, `api/eval/` for the dev/eval-only routers, `api/ws/`), the schema split, the `build_container` split, domain move-outs (`feedback_domain.py` → ze-memory, `interruption_domain.py` → ze-proactive, `WORKSPACE_RUN_COMPLETED` → ze-workspace, `testing.py` → `tests/support/`), X-25, K-11, K-12, S-05, O-07 – O-09 (inline SQL to the owning packages), A-20, A-21. Update `Makefile`, `scripts/codegen.ts`, `docker-compose.yml` in the same floor; no alias modules. Owns: `apps/ze-api/**`, the three new files in ze-memory, ze-proactive and ze-workspace, `scripts/codegen.ts`, `docker-compose.yml`. Depends: CF-05, CF-06, CF-08. Gate: 181 (`websocket/confirmation.py`). Migration: none. Operation IDs and paths do not change here; regenerate the client only to prove that.

**CF-10 — ze-web and ze-ui tidy.** Scope: W-01 – W-03 (unused files, exports and deps; check the chart kit's public surface first) and O-05 (turn on `boundaries/element-types` in `.eslintrc.cjs` and fix the 6 upward and 31 cross-slice imports). Owns: `apps/ze-web/**` except files CF-06 changed, `packages/ze-ui/**`, `apps/ze-web/.eslintrc.cjs`. Depends: CF-06. Gate: 181 (`TopBar` → notification bell). Migration: none.

**CF-11 — finance, messenger, google, news.** Scope: X-21 (delete the Trading212 order methods), X-22 (delete the finance risk stubs), T-05 (`poll_replies`), T-07 messenger part (wire `contribution_from_outbound` or delete it; check phase 136 first), T-09, `MessengerPlugin._action_record_store` (X-23), and the finance and google README rows in M-05. Owns: `plugins/ze-finance/**`, `integrations/ze-trading212/**`, `integrations/ze-google/**`, `plugins/ze-messenger/**` except the honesty import line, `plugins/ze-news/ze_news/registry.py`. Depends: none. Gate: none. Migration: none.

**CF-12 — workspace, proactive, data, eval, sidecar.** Scope: X-06, X-17, X-18, X-19, X-20, T-07 workspace part, M-09, and the sidecar hardening from §0 item 6 (keep references to `_execute` tasks; fixture awaits them; `on_event` → lifespan). Owns: `core/ops/ze-workspace/**` except the new `push_kinds.py`, `ze_proactive/job.py`, `core/kernel/ze-data/**`, `core/ops/ze-eval/**`, `sidecar/**`. Depends: none. Gate: none. Migration: none.

**CF-13 — tooling.** Scope: G-01 (`scripts/graphify_reexports.py`, run after `graphify update .`; the Maestro adds it to the post-land routine), G-03 (`make deadcode` report target with a checked-in vulture whitelist; report only, not a gate), and the claim-vocabulary note from §0 item 4 (a short paragraph in `specs/arch/claim-topology.md` on where `EvidenceRef` lives and the two kind lists). Owns: `scripts/graphify_reexports.py`, `scripts/vulture_whitelist.py`, the `deadcode` block in `Makefile`, `specs/arch/claim-topology.md` (that paragraph). Depends: CF-08 (Makefile). Gate: none. Migration: none.

**CF-14 — System One and loop residue.** Scope: O-01 (one helper kit in `ze_agents/system_one.py` for bar parsing and answer validation; each surface keeps its own `decide()`), S-07 (rename `legacy` in `ze_skills/matching.py`), the `decay.py` re-export (S-03), R-01, R-02, M-12 (only what is still true after 173), and X-26. Owns: `ze_agents/system_one.py` (helpers), `ze_skills/{judge,matching}.py`, `ze_memory/speech_act_judge.py`, `ze_worldstate/{loop_judge,corroboration_judge,decay}.py`, `ze_core/judge.py`, `ze_core/routing/judge.py`, `core/cognition/ze-worldstate/README.md`. Depends: CF-01, CF-03. Gate: 173 and 182. Migration: none. Rerun the offline calibration checks (`--check-sets`) for each surface to prove decisions did not move.

**CF-15 — repo-wide renames.** Scope: S-02 (`ZeCoreError` → `ZeError`, alias deleted) and D3 (plugin imports only via `ze_sdk`: codemod, add missing re-exports, tighten `test_plugin_boundaries.py`). Owns: any file; runs alone. Depends: every other code floor (CF-01 – CF-14). Gate: all of those landed. Migration: none.

**CF-16 — docs.** Scope: D-09, M-04 – M-08, M-10, M-11, every doc delta logged in the other floors' Handoffs notes (D4), the AGENTS.md dependency graph, migration table, tree and phase/status rows the cleanup changed, and a coverage check against `git diff main...HEAD` across all landed cleanup floors. Follows the `doc-style` skill for public docs. Owns: `AGENTS.md`, `docs/*.md` except `configuration.md`, `README.md`, `specs/README.md`, package READMEs not owned by another floor. Depends: CF-01 – CF-15. Gate: all landed. Migration: none.
