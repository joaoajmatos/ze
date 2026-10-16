# Research: Complexity Routing (182)

Evidence read at `d70b7af7` (branch `182-complexity-routing`), plus the dev database (`ze-postgres-1`, read-only queries) on 2026-10-16. Items marked **(decided)** were confirmed by the user at scope review on 2026-10-16 (spec Clarifications).

## R0 — Ground truth

| Fact | Evidence |
|---|---|
| Tier only matters for companion, research, goals | `model_simple = "anthropic/claude-haiku-4-5"` on `ze_personal/agents/companion/agent.py:124`, `research/agent.py:40`, `ze_automation/agents/goals/agent.py:78`; their `model` is Sonnet 4.5. Calendar, reminders, messenger, finance run Haiku; workflow runs Sonnet; none declares `model_simple`. |
| Tier is resolved at route time | `EmbeddingRouter._resolve_model(agent, complexity)` (`router.py:128`) writes `SubTask.model` on every path: `_envelope`, `_single_agent_envelope`, `route_forced`; `decompose` patches each subtask (`nodes/routing.py:104-118`); `_open_query_envelope` (`nodes/context.py:173`). |
| Model consumers | `execute_tool` / `draft_response` pass `subtask.model` into `AgentContext.model` (`nodes/execution.py:220,379,480`); `BaseAgent._model(ctx)` falls back to `self.model`. `capability_check` and the spend budget never read the model. |
| Delegates ignore tiers and overrides | `delegate_to_agent` builds the sub-context with `model=None` (`ze_agents/delegate.py:326`), so a delegated specialist runs `self.model`, without `models.overrides`. Out of scope; recorded as a follow-up. |
| Overrides win over both tiers | `resolve_model(key, declared, config)`: `models.overrides[agent]` beats the declared model, so with an override both tiers resolve to the same model. |
| The regex rarely picks the light model | `routing_log` (dev, 2026-05-17 → 2026-10-15): companion complex 140 / simple 0; goals 84 / 10; research 34 / 11. 21 of 279 tiered turns (7.5%) ran Haiku. |
| The routing request already carries a Score | `judge.py` `Q_COMPLEXITY`; consumed only when `complexity_lookup_max` is set; it is `null` in `config.yaml`. 167 R10: the Score does not separate the levels (a multi_hop row at 0.02, a single_tool row at 0.04, below the lookup maximum of 0.33). |
| Routing state is thin | `build_judgment_state` (`orchestration/judgment_state.py`): user text (2000), last 4 messages × 240 chars, dropped after 30 min idle, `routing_hints` (600); `_JUDGE_SUFFIX` = "Judge the user's words; history and context are background only." |
| Context exists only after routing | `fetch_context` builds memory (`store.retrieve`, 2000 tokens), the resume recap (session summary, open loops, loop offers, in-flight workflows), procedures, the screen-context workflow note and the conductor hint. `match_skills` then sets `active_skills`. |
| `routing_log.complexity` / `model_selected` are write-only | Written by `PostgresRoutingStore.write_log` (`store.py:30`); `list_routing_log` (`rest.py`) and `RoutingLogEntry` do not select them; no web reader. |
| System One latency | 7 batched requests in dev `messages.trace` judgments: speech-act 451 ms p50 / 528 max; routing 593 ms. Timeout `system_one.timeout_ms: 2000`. The ADR's "~100 ms" is the provider figure, not what Ze sees. Sample is small; the calibration runner records latency on every row (R8). |

## R1 — Where the tier is decided (headline) **(decided: A)**

The user's requirement: judge the task at hand, which may span earlier turns, memory, an active goal or workflow, a matched skill, and what the task will involve.

| Option | What it is | Task context it sees | Added latency when on | Cost | Verdict |
|---|---|---|---|---|---|
| **A. Tier step after `match_skills`** | New graph node `choose_tier` between `match_skills` and `capability_check`. Routing always assigns the full model; the node may swap in `model_simple`. | Conversation (wider window), recap or session summary, retrieved memory, focus (screen workflow, in-flight goal/workflow, invoked procedure), matched skill, routed agent's description and tools. All of it. | One System One request, sequential: ~0.45–0.6 s (dev), 2 s cap; only on tierable turns. | One Jev request (input billed, output free); negligible next to one Sonnet call. | **Recommended.** Only option that sees everything the user listed. Clean separation: routing picks *who*, the tier step picks *how hard*. Off = no request, no latency. |
| A′. Same, run beside `match_skills` | Start the tier request in parallel with the skill request. | Everything except the matched skill. | ~0 extra on turns where skill gating also calls System One; otherwise as A. | As A. | Fallback if the user rejects A's latency. Loses the skill signal, which is weak for tiering (a skill narrows tools; it rarely changes how hard the task is). Adds concurrency to a node that today is simple. |
| B. Haiku "task framing" first | A Haiku call restates the task ("the user wants Ze to carry out the 5-step plan above"), then System One judges the restatement. | Whatever the framing prompt gets. | One Haiku call (~1–2 s) **plus** the System One request. | One Haiku call per tiered turn: costs more than the light model saves on short turns. | Rejected. Pays an LLM call to save an LLM call, adds the most latency, and is a generative step in a judgment path (ADR non-fit: System One cannot write text, but that is no reason to put Haiku on the critical path). Anaphora is better solved by giving the judge the conversation (A). |
| C. Start light, escalate in the loop | Run the light model; a harness hook switches to the full model on signals (tool-call count, a failed tool, a long plan, the agent asking). | Live signals, after the fact. | None up front; a restart or mid-loop switch on escalation. | Saves the most when it works; pays twice when it escalates. | Strong **follow-up**, complementary to A: A decides the start, C rescues a wrong downgrade. Not this phase: needs a model switch inside `agentic_loop` (ze-agents `HarnessHook`), streamed-token handling when the first model already spoke, and its own eval. It cannot fix the first reply's quality for companion (no tools on a reflective answer). |
| D. Per-subtask tiers on decompose/conductor | Judge each subtask or each delegate. | Subtask prompt only (decompose already strips context). | One request per subtask or delegate. | Low savings: compound and conductor turns are rare and genuinely multi-step. | **Deferred.** Conductor turns stay full by definition (FR-012). Revisit only with data showing many cheap delegates. |
| E. Keep it in the routing request, wider history | Replace the Score with the Noul inside the batched routing request; raise the history window. | Conversation only (routing runs before memory, recap and skills). | 0 (same request). | 0 extra. | Rejected: fails the user's pinned requirement (no memory, recap, goal, workflow or skill), and ties tiering to the routing surface being on and calibrated. |

**Latency note.** Option A adds the request to time-to-first-token on tierable turns only (companion, research, goals; single agent; surface on). On light turns, Haiku's faster first token offsets part of it. The acceptance rule reports p50/p90 latency per language but does not gate on it. The user accepted A with latency reported only (scope review 2026-10-16).

## R2 — Question shape **(decided: one Noul, one bar)**

- **Decision**: one Noul `needs_deep_reasoning`, alone in its request, `max_attempts=1`. Light model only when P(yes) ≤ `simple_max`. Unsure (≈ 0.5) is "yes" for safety: the bar will sit well below 0.5.
- **Instruction (draft, tuned on the tuned set only)**: "Will doing this task well need a stronger model: careful reasoning, weighing options, synthesis across several sources, planning, nuanced personal or emotional judgment, or several dependent steps? Answer no for greetings, thanks, acknowledgments, a single fact or status lookup, a short confirmation, or one routine action. Judge the task the user is trying to get done, not only their last message: use the conversation, recap, memory, focus and skill to work out what 'it', 'that plan', 'go ahead' or 'the other one' refers to."
- **Why a Noul**: the decision is one yes/no (ADR primitives table; pin 7: one narrow question). A single bar is the smallest thing a ~50-row-per-language set can calibrate.
- **Rejected**: (a) keep the 3-level Score — 167 R10 showed it does not separate; (b) a two-option Choice {light, full} — same decision, but peakedness is not P(yes), and the ADR reserves Choice for closed sets of more than a yes/no; (c) two Nouls (reasoning, multi-step) — two bars on a small set, and no evidence one Noul is not enough. Revisit (c) only if the tuned set shows the single Noul conflates them.
- **Gold label definition (for both sets)**: `full` when a strong model's reply would be materially better: reasoning, deciding between options, synthesis or comparison, planning, long writing, an emotional or personal conversation that needs care, or a multi-step task with dependent tool calls. `simple` when a small model would do as well: greeting, thanks, acknowledgment, a single fact or status lookup, a short confirmation, a routine single action, a short reformat. When unsure, label `full` (harm-first).

## R3 — Task state (FR-006)

Built by a new `build_tier_state(state)` in `ze_core/orchestration/judgment_state.py`, beside `build_judgment_state` (which routing and skills keep unchanged). Named fields only (pin 6):

| Field | Source | Cap |
|---|---|---|
| `task` | `image_caption` or `prompt` | 2000 chars |
| `conversation` | last 8 messages of `agent_context.messages` before the current one, each "role: text" | 400 chars per message, 2400 total |
| `recap` | `agent_context.resume_recap` when the session resumed (history is empty then) | 800 |
| `memory` | top retrieved items from `memory_context` (the same chunks `_extract_memory_chunks` builds for the trace), text only | 5 items × 200 chars |
| `focus` | `routing_hints` (the ze-automation pre-route node's active goals and their current step or pending gate); `agent_context.screen_context_note` (workflow in view); `procedure_matches` names; in-flight workflow lines from the recap | 600 |
| `skill` | names and descriptions of `agent_context.active_skills` | 300 |
| `agent` | routed agent name, `routing_criteria or description` (`criterion_for`), and its tool names | 600 |

Why 8 × 400: a planning exchange that defines "that plan" is typically 4–10 messages with assistant replies far longer than 240 chars; the cap keeps the request under ~8 kB. **Verify at implement** on the tuned set's longest rows; caps are constants, not config.

## R4 — Coverage (FR-011–FR-013)

- Router paths (`_envelope`, `_single_agent_envelope`, `route_forced`), `decompose`, `_open_query_envelope` and `apply_conductor_rewrite` all assign the **full** model.
- `choose_tier` judges when: exactly one subtask, `not envelope.is_compound`, `state["conductor_hint"]` is empty, and `resolve_agent_model(agent, "simple") != resolve_agent_model(agent, "full")`. Otherwise `decided_by` is `compound` or `no_simple_model` and no request is made.
- `decompose` producing one subtask (Haiku said single agent) is tierable; that is a normal single-agent turn.
- Resume after `await_confirmation` re-enters at `execute_tool`; `choose_tier` already ran and its envelope is in state. Retry (165/180) re-runs the graph and judges again.

## R5 — Flag location **(decided: own surface)**

`system_one.surfaces.complexity: {enabled: false, simple_max: null}`. Parsed by `complexity_surface_config(settings)` in `ze_core/routing/tier.py`, same tolerant shape as `routing_surface_config` (invalid bar → `None` with a warning). Reasons: separate request, separate bar, separate calibration, separate enable commit; the routing surface can be on while tiering is off, or the reverse. `system_one.surfaces.routing.complexity_lookup_max` is deleted from config, `RoutingSurfaceConfig`, docs and the routing calibration script.

## R6 — Trace and storage **(decided)**

- `TierTrace` dataclass on `MessageTrace.tier` (`agent`, `tier`, `decided_by`, `model`); `TierTraceResponse` on `MessageTraceResponse` and `MessageTraceEntry`; one partial `trace_update` after `choose_tier` (`turn.py`, beside the `embed_route` partial). Judgment row `needs_deep_reasoning` appended to `state["judgments"]`.
- `routing_log`: drop `complexity` and `model_selected` (`zc0NN_drop_routing_log_tier`). Rejected: leave the columns and write the full model or NULL. Dropped (decided), because a route-time model would be wrong once the tier step changes it, and nothing reads them (pre-v1 Principle VIII).
- Web: one tier line in `RoutingBadge` ("Light model · System One", "Full model · surface off", …), fed from `trace.tier`. `JudgmentsSection` already renders the Noul row.

## R7 — Acceptance rule **(decided)**

Per language on the held-out set, at the frozen `simple_max`:

1. **Harm cap**: zero false downgrades (gold `full` judged light). Same strictness as 167's "zero harmful trusts" and 172's "zero false promotions".
2. **Savings floor**: light-model recall ≥ 0.5 over gold-`simple` rows. Below it the request costs latency for too little saving; the feature is not worth turning on.
3. **Reliability**: ≤ 10% of rows skipped or invalid.

Reported, not gating: precision of the light decision, false-downgrade count on the tuned set, latency p50/p90, per-agent counts, the Noul histogram by gold tier.

Alternatives rejected at scope review: (a) allow one false downgrade per language with recall ≥ 0.6; (b) a savings share over all rows instead of recall (the authored mix sets that share, not real traffic); (c) gating on p90 latency.

## R8 — Calibration sets and runner

- **Files**: `eval/calibration/complexity.jsonl` (tuned), `eval/calibration/complexity_holdout.jsonl` (held-out), `eval/calibration/complexity.py` (runner), `make calibrate-complexity` (live, costs credits) with `--check-sets` (offline) and `--set holdout`.
- **Row schema** (both files): `id`, `lang` (`en`|`pt`), `agent` (`companion`|`research`|`goals`), `conversation` (list of `{role, content}`, may be empty), `recap` (str|null), `memory` (list of short strings), `focus` (str|null), `skill` (`{name, description}`|null), `prompt`, `gold_tier` (`simple`|`full`), `kind` (`single`|`multi_turn`|`anaphoric`|`resumed`|`with_memory`|`with_focus`|`with_skill`), `why` (one line).
- **Sizes**: tuned ≥ 40 rows per language; held-out ≥ 24 per language with ≥ 10 gold `simple` and ≥ 10 gold `full` per language. Every agent in both tiers per language. At least 40% of rows have a non-empty conversation; at least 6 anaphoric rows per language per set, both directions.
- **Runner**: builds the state with the production `build_tier_state` over a synthetic `AgentState`/`AgentContext` built from the row (so the bar is the bar production sees, the 167 R5 lesson); calls the real client with `max_attempts=1`; records answer, latency and skip reason; prints the per-language table and the suggested bar on `tuned`; prints the verdict on `holdout` at the bar passed with `--simple-max` (the frozen value). Never collected by pytest.
- **Bar rule (FR-017)**: highest Noul value strictly below every tuned `full` row's value, i.e. `min(full_scores) - ε`, rounded down to 0.05; `None` if no tuned `simple` row lies below it. Mirrors the 167 R10 fix.

## R9 — Held-out authoring **(decided)**

The Spec Architect wrote the brief (`contracts/holdout-brief.md`), which is self-contained. A fresh junior, Quoin, gets only that path, writes `complexity_holdout.jsonl` and commits it before the ENG lead writes the tuned set. Quoin never sees the tuned set, the runner or the tier module; the ENG lead never opens the held-out file before the verdict run. Rejected: the Spec Architect writing it (the architect drafted the question wording, so it would not be blind).

## R10 — Cost arithmetic

Haiku 4.5 is about one third of Sonnet 4.5's price per token. A Jev request bills input only (~2–3 k tokens of state). At the regex's 7.5% light share the saving was small; a calibrated Noul with recall ≥ 0.5 on light turns should send a larger share, but the real share depends on traffic, so the phase does not promise a number. Telemetry already attributes System One cost; `choose_tier` sets the agent context to `router` like `embed_route` (164 R11) so the cost lands under routing.

## R11 — Follow-ups recorded (not this phase)

- In-loop escalation (R1 option C).
- `delegate_to_agent` ignores `models.overrides` (R0).
- Per-subtask tiers (R1 option D).
- A later re-calibration if `typesafe/jev-1.13` changes (ADR pin 10).
