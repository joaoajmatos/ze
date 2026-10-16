# Research: Complexity Routing (182)

Evidence read at `d70b7af7` (branch `182-complexity-routing`), plus the dev database (`ze-postgres-1`, read-only queries) on 2026-10-16. Items marked **(decided)** were confirmed by the user at scope review on 2026-10-16 (spec Clarifications).

## R0 — Ground truth

| Fact | Evidence |
|---|---|
| Tier only matters for companion, research, goals | `model_simple = "anthropic/claude-haiku-4-5"` on `ze_personal/agents/companion/agent.py:124`, `research/agent.py:40`, `ze_automation/agents/goals/agent.py:78`; their `model` is Sonnet 4.5. Calendar, reminders, messenger, finance run Haiku; workflow runs Sonnet; none declares `model_simple`. |
| Tier is resolved at route time | `EmbeddingRouter._resolve_model(agent, complexity)` (`router.py:128`) writes `SubTask.model` on every path: `_envelope`, `_single_agent_envelope`, `route_forced`; `decompose` patches each subtask (`nodes/routing.py:104-118`); `_open_query_envelope` (`nodes/context.py:173`). |
| Model consumers | `execute_tool` / `draft_response` pass `subtask.model` into `AgentContext.model` (`nodes/execution.py:220,379,480`); `BaseAgent._model(ctx)` falls back to `self.model`. `capability_check (now `preflight`, after 181)` and the spend budget never read the model. |
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
| **A. Tier step after `match_skills`** | New graph node `choose_tier` between `match_skills` and `capability_check (now `preflight`, after 181)`. Routing always assigns the full model; the node may swap in `model_simple`. | Conversation (wider window), recap or session summary, retrieved memory, focus (screen workflow, in-flight goal/workflow, invoked procedure), matched skill, routed agent's description and tools. All of it. | One System One request, sequential: ~0.45–0.6 s (dev), 2 s cap; only on tierable turns. | One Jev request (input billed, output free); negligible next to one Sonnet call. | **Recommended.** Only option that sees everything the user listed. Clean separation: routing picks *who*, the tier step picks *how hard*. Off = no request, no latency. |
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
| `agent` | **removed** (FR-006 amended 2026-10-16, see R12): the routed agent's scope text describes what it covers, not how hard the task is, and added noise to the judgment on the tuned set | n/a |

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


## R12 — Tuning notes and freeze (T029, T030)

Date: 2026-10-16. Tuned set `eval/calibration/complexity.jsonl` (cx-001 to cx-094, 47 EN and 47 PT), model `typesafe/jev-1.13`, `timeout_ms` 2000, concurrency 4, `max_attempts=1`, state from the production `build_tier_state`. The held-out file was never read: only `--check-sets` ran over it, which prints counts, plus one aggregate state-size check that printed total characters only. Live runs used: 6 of the 8 the user approved. No run had a skipped or invalid row.

### Runs

"False downgrades" are `full` rows judged light at the bar used; "light recall" is light-judged over gold-`simple` rows.

| Run | State variant | Bar used | EN false / recall | PT false / recall | Lowest `full` | Highest `simple` | Rule bar (highest step below lowest `full`) |
|---|---|---|---|---|---|---|---|
| 1 | A: `agent` = routing_criteria text, 600 cap | 0.30 | 0 / 22 of 23 | 0 / 23 of 23 | 0.30 to 0.35 (not printed) | typical below 0.30, outlier cx-007 0.34 | 0.30 |
| 2 | A, repeat of run 1 | 0.30 | 0 / 22 of 23 | 0 / 23 of 23 | same band | typical below 0.30, outlier cx-007 0.36 | 0.30 |
| 3 | B: tools first (250) then description (349) | 0.40 | 0 / 22 of 23 | 0 / 23 of 23 | 0.42 | typical 0.30, outlier cx-007 0.43 | 0.40 |
| 4 | C: no `agent` field (`--without agent`) | 0.55 | 0 / 23 of 23 | 0 / 23 of 23 | 0.60 | cx-007 0.45, next cx-039 0.38 | 0.55 |
| 5 | C on the final code (agent field removed) | 0.55 | 0 / 23 of 23 | 0 / 23 of 23 | 0.56 | cx-007 0.44, next cx-039 0.40 | 0.55 |
| 6 | C on the final code, at the frozen bar | 0.40 | 0 / 22 of 23 | 0 / 23 of 23 | 0.56 | cx-007 0.47 (kept full), cx-039 0.400 (counted light) | 0.55 |

Latency (provider time, run 6): EN p50 529 ms, p90 802 ms; PT p50 547 ms, p90 818 ms. Runs 1 to 5 stayed within p50 511 to 549 ms and p90 602 to 812 ms.

**Noise.** Runs 4 and 5 sent the same state: the lowest `full` row moved from 0.60 to 0.56 and cx-007 from 0.45 to 0.44, then 0.47 in run 6. Runs 1 and 2 moved cx-007 from 0.34 to 0.36. A single row can move up to about 0.04 between runs; aggregate counts did not change between repeats.

### Decisions

- **Instruction text and caps**: unchanged from the R2 draft and the R3 caps. The classes separated on the first run, so no instruction iteration was needed.
- **`agent` field dropped** (spec FR-006 amended, Clarifications 2026-10-16, Spec Architect approved). A (routing criteria) left a 0.30 to 0.35 floor under the `full` rows; B (the Spec Architect's ruling: description and tool names, tools first) was worse than A because its light outlier (0.43) sat above its lowest `full` row (0.42); C opened a clear gap (lowest `full` 0.56 to 0.60, highest `simple` 0.44 to 0.47). The field describes scope, not difficulty. The state builder no longer reads the agent registry.
- **Bar rule** (spec FR-017 amended): no tuned `full` row judged light; at least 0.15 below the lowest tuned `full` Noul; tuned light recall of at least 0.8 per language; prefer the larger margin. The literal "highest step" rule gives 0.55, which is 0.01 under the lowest `full` row of run 5 and inside the 0.04 noise.

### Freeze (T030), 2026-10-16

- **`simple_max` = 0.40.** Against run 6 and run 5: zero tuned `full` rows judged light; margin to the lowest tuned `full` row 0.16 (0.56 − 0.40; 0.20 against run 4), about four times the measured single-row noise; tuned light recall EN 22 of 23 = 0.957 and PT 23 of 23 = 1.000, both at least 0.8. cx-039 sits at exactly 0.400 and counts as light (a value equal to the bar is light); if it flipped, EN recall would be 21 of 23 = 0.913, still above 0.8. The stop condition from the Spec Architect (lowest `full` row below 0.55) did not trigger: 0.56.
- **State shape, in this order, empty fields omitted**: `task` (image caption or prompt, 2000 chars); `conversation` (last 8 prior messages, current message excluded, 400 chars per message, 2400 total, oldest dropped first); `recap` (800; the resume header, the in-flight workflow block and the unconfirmed-loop block removed); `memory` (top 5 chunks by score, 200 chars each); `focus` (600; routing hints, screen-context note, procedure names, in-flight workflow lines); `skill` (300). No `agent` field.
- **`TIER_INSTRUCTIONS` (`ze_core/routing/tier.py`, verbatim)**:

> Will doing this task well need a stronger model: careful reasoning, weighing options, synthesis across several sources, planning, nuanced personal or emotional judgment, or several dependent steps? Answer no for greetings, thanks, acknowledgments, a single fact or status lookup, a short confirmation, or one routine action. Judge the task the user is trying to get done, not only their last message: use the conversation, recap, memory, focus and skill to work out what 'it', 'that plan', 'go ahead' or 'the other one' refers to.

- **Held-out run, once, after the Maestro's go and Soffit's written confirmation**: `make calibrate-complexity ARGS="--set holdout --simple-max 0.40"`. The runner refuses a second scoring unless `--rerun` is passed. Verdict (FR-016): per language zero false downgrades, light recall at least 0.5, skipped or invalid at most 10%.

### Held-out verdict (T031), 2026-10-16

One live run of the blind held-out set (`eval/calibration/complexity_holdout.jsonl`, 54 rows, 27 EN and 27 PT, written by Quoin in 024bb325 before the tuned set) at the frozen bar: `make calibrate-complexity ARGS="--set holdout --simple-max 0.40"`, model `typesafe/jev-1.13`, `timeout_ms` 2000, `max_attempts=1`, the production `build_tier_state`. Run after the freeze f48ac21f, after the Maestro's go, and after the Spec Architect's and Soffit's written confirmations; the runner's spent marker did not exist before it. The held-out set is now spent for this bar and instruction text (FR-019). A tuned smoke run (run 7, 94 rows) immediately before showed 0 false downgrades and 23 of 23 light recall in each language, one transient timeout (1 of 47 EN rows), lowest `full` 0.60, highest `simple` 0.44.

Full report (histograms and counts only; the runner prints no row text or ids on this path):

```
== Noul histogram by gold tier [en]
bin           simple   full
[0.00,0.05)       1      0
[0.05,0.10)       1      0
[0.10,0.20)       6      0
[0.20,0.30)       5      0
[0.30,0.50)       1      0
[0.50,0.70)       0      3
[0.70,1.00)       0     10

== [en] at simple_max=0.4
  rows=27 simple=14 full=13 light=14 falseDowngrades=0 recall=1.000 (14/14) precision=1.000
  skipped/invalid=0 (0.000) 
  latency ms p50=550 p90=880
  companion  rows= 11 simple=  5 full=  6 light=  5
  research   rows=  9 simple=  5 full=  4 light=  5
  goals      rows=  7 simple=  4 full=  3 light=  4

== Noul histogram by gold tier [pt]
bin           simple   full
[0.05,0.10)       3      0
[0.10,0.20)       5      0
[0.20,0.30)       4      0
[0.30,0.50)       1      1
[0.50,0.70)       1      1
[0.70,1.00)       0     11

== [pt] at simple_max=0.4
  rows=27 simple=14 full=13 light=13 falseDowngrades=0 recall=0.929 (13/14) precision=1.000
  skipped/invalid=0 (0.000) 
  latency ms p50=552 p90=985
  companion  rows= 11 simple=  5 full=  6 light=  4
  research   rows=  9 simple=  5 full=  4 light=  5
  goals      rows=  7 simple=  4 full=  3 light=  4

== HELD-OUT VERDICT
simple_max: 0.4
[en] ENABLE  falseDowngrades=0 recall=1.000 (14/14) skipped=0.000 precision=1.000
[pt] ENABLE  falseDowngrades=0 recall=0.929 (13/14) skipped=0.000 precision=1.000
OVERALL: ENABLE
```

| | EN | PT |
|---|---|---|
| (a) false downgrades (`full` judged light) | 0 | 0 |
| (b) light recall (gold `simple` judged light) | 14 of 14 = 1.000 | 13 of 14 = 0.929 |
| (c) skipped or invalid | 0 of 27 = 0.000 | 0 of 27 = 0.000 |
| precision of the light decision (reported) | 1.000 | 1.000 |
| latency p50 / p90 (reported) | 550 ms / 880 ms | 552 ms / 985 ms |
| verdict | **ENABLE** | **ENABLE** |

**Overall: ENABLE** (FR-016: zero false downgrades, light recall at least 0.5, skipped or invalid at most 10%, in both languages).

Margin on the blind set, stated plainly because the tuned set did not predict it: the lowest PT `full` row sits in the 0.30 to 0.50 bin; since it was not judged light at 0.40 it lies between 0.40 and 0.50, within 0.10 of the bar (tuned lowest `full` was 0.56 to 0.60). The tuned-set noise (single rows move up to about 0.04 between runs) is about half that gap. The verdict is ENABLE, but the harm cap has less slack on held-out data than the tuned margin of 0.16 suggested. The set cannot be re-scored to measure it.

### Routing check after the Score cut (T032, report-only), 2026-10-16

`make calibrate-routing` once on the tuned `routing.jsonl` (70 rows, 30 EN and 30 PT per language scored, `k` 9, model `typesafe/jev-1.13`), with the routing request now carrying two questions (agent, multi_specialist) and no Score. Acceptance verdict of the script: **PASS** (not gating here).

| | 167 (2026-10-12, held-out `routing_holdout` / `routing_holdout2`) | 182 (this run, tuned `routing.jsonl`) |
|---|---|---|
| EN accuracy | 1.000 | 29 of 30 = 0.967 |
| PT accuracy | 1.000 | 30 of 30 = 1.000 |
| ECE | 0.041 and 0.014 | 0.043 |
| research to companion trusted misses | 0 | 0 |
| harmful trusts at `choice_trust` 0.5 / `multi_specialist_hold` 0.5 | 0 | 0 |
| `none` precision / recall | | 1.00 / 1.00 |
| suggested bars | 0.5 / 0.5 shipped | 0.8 / 0.55 (the script's suggestion; the shipped bars stay) |

The one EN miss is a `loops` row predicted as `companion`. It is one of the four training rows phase 171 appended (T034) after 167 recorded its training figures (26 of 26 on 52 rows, ECE 0.034), and it is a context-dependent confirmation sentence. 167's tuned and held-out figures are for different row sets, so the comparison is indicative only; no pre-182 baseline exists for the 171 rows, and I did not spend a second live run to build one. A drop beyond 167's figures is not shown (accuracy 0.967 against 1.000 on one row; ECE 0.043 against 0.041).

### Enabling (T033) authorisation, 2026-10-16

FR-020 and T033 require the user's go-ahead, relayed by the Maestro, before the enable commit. After the verdict report (265330fe) the Maestro answered, and the enable commit followed as 2996e4c2 (19:42:46 +01:00), separate from the implementation commits:

> Maestro: the user approves. ASK 1: do T033 now (separate commit: system_one.surfaces.complexity enabled: true, simple_max: 0.40, config comment cites the verdict and the thinner PT held-out margin). ASK 2: run T032 once (report-only routing calibration). ASK 3: floor 181 has not landed yet (Halyard is merging main into it); I will tell you. Continue T034-T040, Soffit final pass, then QA e2e (I will assign Tally).

The same message is quoted in the 182 Handoffs note. The enable commit touches only `config.yaml`, its container test and the task bookkeeping.
