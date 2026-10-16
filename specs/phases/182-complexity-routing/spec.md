# Feature Specification: Complexity Routing

**Feature Branch**: `182-complexity-routing`

**Created**: 2026-10-16

**Status**: Ready to implement (scope signed off by the user 2026-10-16); surface ships off

**Input**: User description (via the Maestro): "Complexity only picks the model tier for agents with `model_simple` (companion, research, goals: Sonnet 4.5 vs Haiku 4.5). The decider is the English-only regex `ComplexityEstimator`, biased to 'complex'. System One already asks a graded complexity Score on every routing call, but it did not calibrate (167: 0.16/0.17 per set, 0.02 combined). There is no way to turn tiering off. Pinned: (1) a feature flag that ships off, so every agent uses its full model, turned on in a separate commit only after a held-out ENABLE in EN and PT; (2) hard-cut the regex estimator, System One decides, and off/skip/invalid/uncalibrated means the full model; (3) spec now, build after the user signs off." Added mid-spec as a core requirement: "Complexity must NOT be judged from the latest message alone. The judge has to understand the task at hand: what the user is actually trying to get done, which may span earlier turns, retrieved memory, an active goal or workflow, a matched skill, or what the task will likely involve."

**Governed by**: [`specs/arch/system-one-models.md`](../../arch/system-one-models.md) (pinned rules 2, 5, 6, 7, 10; O2 implementation notes for 164 and 167), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md), [`specs/arch/companion-conductor-roadmap.md`](../../arch/companion-conductor-roadmap.md). Phases [164](../164-routing-choice-after-e5/spec.md), [167](../167-routing-choice-criteria/spec.md) (R10: why the Score cannot set a bar), [168](../168-loop-extraction-gate/spec.md) and [172](../172-corroboration-promotion/spec.md) (tuned set, frozen bars, one blind held-out verdict).

**Depends on**: Phases 162, 164 and 167 Implemented (they are). No dependency on floors 181 or 173; the migration number is chosen at implement time (see plan).

**Does not change**: agent selection (E5 shortlist, the routing Choice, its bars `choice_trust` / `multi_specialist_hold` / `shortlist_k`, the 160 cosine path), Haiku `decompose`, the 153/155 conductor rewrite, `delegate_to_agent` (delegated specialists keep running their own declared model), `CapabilityGate`, the spend budget, skills gating (166), speech-act (163), the loop gate (168).

**Doctrine function served**: executive function (Ze spends deliberate effort where the task needs it). It is a cost and latency lever, not a new capability.

---

## Overview

Three agents declare a lighter `model_simple`: companion, research and goals. For each turn routed to one of them, Ze picks the full model or the light one. Today that choice is a word-count regex that knows English only. It almost never picks the light model: in the dev database, companion was "complex" on 140 of 140 turns, goals on 84 of 94 and research on 34 of 45. Portuguese and short prompts land on the full model by default, and short prompts that need deep work ("ok, go ahead with that plan") are judged on four words.

The decision is also made in the wrong place. It runs inside routing, before Ze has retrieved memory, built the resume recap, matched a skill or looked at the active workflow. The only context it sees is the last four messages, 240 characters each, and its instruction says "judge the user's words; history is background only". That cannot tell "ok do it" after a long planning exchange from "ok thanks".

This phase replaces the regex with one System One judgment that runs **after** Ze has gathered the turn's context, asks about **the task the user is trying to get done**, and can only ever downgrade a turn to the light model when it is confident the light model is enough. Everything else runs on the full model. The surface ships off; with it off, every agent always runs its full model.

## Clarifications

### Session 2026-10-16 (scope review)

The user pinned the flag, the hard cut and the "task at hand" requirement before the spec was written. The answers below were given by the user and relayed by the Maestro; each matches the Spec Architect's recommendation. Alternatives are recorded in [research.md](./research.md).

- Q: Where is the tier decided, so that it judges the task at hand? → A: **(user)** A new graph node, `choose_tier`, after `fetch_context` and `match_skills` and before `capability_check`. Routing always assigns the full model; `choose_tier` may swap in `model_simple`. Its state carries the conversation, the resume recap, retrieved memory, active goals and the workflow in view, the matched skill, and the routed agent's criteria and tools. Starting on the light model and escalating inside the agent loop (research R1 option C) is a follow-up phase, not this one.
- Q: Question shape? → A: **(user)** One Noul, `needs_deep_reasoning`, and one bar, `simple_max`. The light model only when the Noul is at or below the bar. The graded routing Score is hard-cut.
- Q: Acceptance rule? → A: **(user)** Per language on the held-out set, at the frozen bar: zero false downgrades, light-model recall at least 0.5, skipped or invalid rows at most 10%. Latency is reported, not gating (FR-016).
- Q: `routing_log.complexity` and `model_selected`? → A: **(user)** Dropped in a ze-core `zc` migration, numbered at build time after floors 181 and 173 land (FR-015).
- Q: Who writes the blind held-out set? → A: **(user)** A fresh junior (Quoin) given only [contracts/holdout-brief.md](./contracts/holdout-brief.md). It is committed before the tuned set exists, and the junior never sees the tuned set (FR-019).
- Q: Flag, coverage and trace? → A: **(user)** Own surface `system_one.surfaces.complexity` (`enabled: false`, `simple_max: null`); `complexity_lookup_max` deleted. Single-agent turns only; compound and conductor turns keep the full model with no request; delegated specialists unchanged. `MessageTrace.tier` plus the judgment row and one line in the web Routing section.
- Note: shipping off moves the 7.5% of tiered turns the regex sent to Haiku (21 of 279 in dev) onto the full model until the surface is enabled. Accepted with the scope.

### Session 2026-10-16 (tuning, before the freeze)

Decided by the Spec Architect (Corbel) on the ENG lead's (Purlin) tuned-set evidence. Relayed to the user through the Maestro; the held-out verdict run (T031) waits for the Maestro's go.

- Q: Keep the `agent` field in the tier state? → A: **Dropped (amends FR-006).** Tuned set, 94 rows (47 EN, 47 PT), same instructions, zero false downgrades in every variant; the margin between the lowest `full` Noul and the light rows decides. A (routing criteria, 600 cap): lowest full ~0.31–0.36, light outlier 0.34–0.36, so the classes nearly touch. B (tool names first 250 + description 349): lowest full 0.42, light outlier 0.43, so they overlap. C (no agent field): lowest full 0.60, highest light 0.45, next 0.38, a clear gap. Run-to-run noise is about 0.02. The field describes the agent's scope, not the task's difficulty, and added noise. The task's likely tools and steps are still judged from the task itself: the instruction asks about synthesis, planning and dependent steps, and the conversation, memory, focus and skill fields stay.
- Q: Which bar is frozen, given that FR-017's "highest step below the lowest full row" gives 0.55, only 0.05 under 0.60? → A: **0.40 (amends FR-017).** The binding clause of the acceptance rule is zero false downgrades on unseen rows; light-model recall only needs 0.5. On the frozen-state run (run 5) the lowest tuned `full` Noul is 0.56 (0.60 on run 4 with the same state, so single-row noise reaches about 0.04) and the highest light row is 0.44. At 0.40 the bar sits 0.16 under the lowest `full` row and tuned light-model recall is 22/23 or better per language. The literal rule's 0.55 and the ENG lead's alternative 0.45 (margin 0.11) were rejected: each trades the harm margin for at most one more tuned light row.

### Session 2026-10-16 (held-out verdict, T031)

- Q: What did the single held-out run say at the frozen `simple_max` 0.40? → A: **ENABLE for English and Portuguese.** Per FR-016, EN: 0 false downgrades, light recall 14 of 14, 0 skipped; PT: 0 false downgrades, light recall 13 of 14 (0.929), 0 skipped; latency p50/p90 550/880 ms (EN) and 552/985 ms (PT). The lowest PT `full` row lies between 0.40 and 0.50, within 0.10 of the bar (research R12 has the full report and this caveat). Enabling (T033) still needs the user's go-ahead; the surface stays off in this commit (FR-020).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - With the flag off, every agent runs its full model (Priority: P1)

The phase lands with the surface off. Every turn routed to companion, research or goals runs Sonnet 4.5, whatever the prompt length or language. No System One request is made for the tier, and the trace says the tier came from the flag being off.

**Why this priority**: This is the shipped state (pinned decision 1) and the fail-safe for every other path. It also deletes the regex.

**Independent Test**: With the shipped config, route a short English lookup ("what is DNS"), a short Portuguese one and a long analysis prompt to research and to companion through the graph with a call-counting fake System One client. Every subtask model is the agent's full model, the tier client is never called, and the trace shows tier `full`, decided by `off`.

**Acceptance Scenarios**:

1. **Given** `system_one.surfaces.complexity.enabled: false`, **When** any turn runs, **Then** every subtask uses its agent's full model (after `models.overrides`).
2. **Given** the surface enabled with `simple_max: null`, **When** a turn runs, **Then** the full model is used, a warning is logged once per process, and the trace says `uncalibrated`.
3. **Given** the regex classifier, **When** the codebase is searched, **Then** it no longer exists, and nothing falls back to it.
4. **Given** the routing request, **When** it is sent, **Then** it carries the agent Choice and the multiple-specialist Noul only, not a complexity Score.

---

### User Story 2 - The tier follows the task, not the last message (Priority: P1)

After a ten-message exchange in which the user and companion draft a plan to restructure their week, the user writes "ok, go ahead with that plan". The judgment sees the conversation, the recap and the memory Ze retrieved, recognises a multi-step planning task, and keeps companion on the full model. In the same session, after research answers a quick question, the user writes "and the other one?" meaning the second of two named cities' current time. The judgment sees a single lookup and sends it to the light model. The same holds in Portuguese ("ok, avança com esse plano"; "e a outra?").

**Why this priority**: This is the user's pinned requirement. Judging four words alone is exactly what fails today.

**Independent Test**: With a fake System One client that records the state it is sent, run the tier step on a fixture conversation. Assert the state carries the conversation turns, the recap or session summary, the retrieved memory items, the active workflow or goal in focus, and the matched skill, each capped, and no agent description or tool list; and that the instruction asks about the task the user is trying to get done.

**Acceptance Scenarios**:

1. **Given** a planning exchange followed by "ok go ahead with that plan", **When** the tier step runs, **Then** its state includes the earlier turns that define "that plan".
2. **Given** a session that resumed after the inactivity gap, **When** the tier step runs, **Then** its state includes the resume recap instead of the dropped history.
3. **Given** a turn opened from a workflow page (screen context), **When** the tier step runs, **Then** the workflow in focus is in its state.
4. **Given** a matched skill, **When** the tier step runs, **Then** the skill's name and description are in its state.
5. **Given** the live calibration, **When** the held-out set is scored, **Then** its anaphoric follow-ups are scored like every other row and count toward the acceptance rule.

---

### User Story 3 - Light turns get the light model, only when System One is sure (Priority: P1)

With the surface enabled and calibrated, "thanks, that's all", "what's the capital of Australia", "obrigado!" and "mark the reading goal done" go to Haiku; "help me decide between the two job offers", "compare these three laptops for my use", "o que achas da minha ideia de mudar de casa?" stay on Sonnet. An unsure answer keeps Sonnet.

**Why this priority**: The savings. Without this the flag can never usefully be on.

**Independent Test**: With a fake client answering the Noul at, below and above `simple_max`, the subtask model is the light model only at or below the bar; a skip, an error, a timeout or a malformed answer gives the full model.

**Acceptance Scenarios**:

1. **Given** the Noul at or below `simple_max`, **When** the tier step runs, **Then** the subtask model is the agent's `model_simple` (after `models.overrides`) and the judgment row is consumed.
2. **Given** the Noul above `simple_max`, **When** the tier step runs, **Then** the full model is used and the judgment row is consumed.
3. **Given** a client skip, timeout, error or invalid answer, **When** the tier step runs, **Then** the full model is used and the trace says why.
4. **Given** an agent with no `model_simple`, or a `model_simple` equal to its full model, **When** the tier step runs, **Then** no System One request is made.

---

### User Story 4 - Compound and conductor turns stay on the full model (Priority: P2)

"Research the best e-bikes and add a reminder to buy one on Friday" becomes a conductor turn: companion conducts, specialists are delegated. That turn runs companion's full model and makes no tier request. A parallel compound turn ("what's on my calendar and what's the weather") keeps each subtask's full model.

**Why this priority**: Multi-agent turns are multi-step by definition, and the 153/155 conductor must not regress.

**Independent Test**: For a compound envelope and for a conductor-rewritten envelope, the tier step makes no request, leaves every subtask on its full model and records tier `full`, decided by `compound`.

**Acceptance Scenarios**:

1. **Given** an envelope with more than one subtask, or `is_compound`, or a conductor hint, **When** the tier step runs, **Then** no request is made and every subtask keeps its full model.
2. **Given** a conductor turn, **When** companion delegates, **Then** each delegated specialist runs its declared model, as before this phase.

---

### User Story 5 - The tier is explainable (Priority: P2)

Opening the trace for a reply shows, in the Routing section, which model tier ran and why ("Light model · System One" or "Full model · surface off"), and the judgment row with its probability. The live trace panel shows the same while the turn streams.

**Why this priority**: Calibration and debugging need it; the user asked for tier and decided-by on the trace.

**Independent Test**: A trace built from a turn with each `decided_by` value round-trips through the trace REST response and the `trace_update` frame, and the Routing section renders the tier line for each.

**Acceptance Scenarios**:

1. **Given** a finished turn, **When** its trace is fetched, **Then** it carries `tier` with agent, tier, decided by and model.
2. **Given** a streaming turn, **When** the tier step finishes, **Then** a partial `trace_update` frame carries `tier`.
3. **Given** the trace panel, **When** the Routing section renders, **Then** it shows the tier and the reason in plain words.

---

### User Story 6 - The surface is enabled only after a blind held-out ENABLE (Priority: P1)

The implementer builds a tuned set and a calibration command, chooses `simple_max` on the tuned set and freezes it. A held-out set, written from a brief by an author who never sees the tuned set or the bar, is scored once. The result is written down as ENABLE or KEEP OFF per language. Only an ENABLE for both English and Portuguese allows a separate commit that turns the surface on.

**Why this priority**: Pinned decision 1. The 167 Score never earned a bar; this one must earn it on unseen rows.

**Independent Test**: `make calibrate-complexity ARGS="--check-sets"` validates both files offline (schema, language balance, required row kinds) with no network call. A unit test runs the scorer on fake answers and checks the verdict logic, including a single false downgrade forcing KEEP OFF.

**Acceptance Scenarios**:

1. **Given** the tuned set, **When** the bar is suggested, **Then** it follows FR-017: no tuned `full` row judged light, at least 0.15 under the lowest tuned `full` Noul, and tuned light-model recall of at least 0.8 per language; or none when no such bar exists.
2. **Given** the frozen bar, **When** the held-out set is scored once, **Then** the report prints, per language, false downgrades, light-model recall, precision, latency p50/p90, and the verdict.
3. **Given** KEEP OFF, **When** the phase closes, **Then** the config keeps `enabled: false` with a dated comment and the figures, and the docs say "calibrated, not enabled".

---

### Edge Cases

- **Image turns**: the state uses the caption, as routing does today.
- **Retry (165/180)**: a retry re-runs the graph, so the tier is judged again; the retried reply may run a different tier, and the trace says which.
- **Confirmation resume**: the tier is fixed before `capability_check`; resuming after a confirmation does not ask again.
- **Open-query reroute**: `fetch_context` may reroute to companion; the tier step runs after it and judges the rerouted agent.
- **Forced eval route**: the tier step runs as for any single-agent turn, so evals exercise it.
- **`models.overrides`**: the full model and the light model both go through the existing override resolution.
- **Global `system_one.enabled: false`**: the surface counts as off.
- **Empty context**: a first turn with no history, memory or skill sends only the task and the agent fields.
- **Goal and workflow executors** outside the conversation graph: not covered; they choose their own models as today.

## Requirements *(mandatory)*

### Functional Requirements

**Flag and fail-safe**

- **FR-001**: The tier MUST be controlled by a surface `system_one.surfaces.complexity` with `enabled` (bool) and `simple_max` (number in [0, 1] or null). It MUST ship `enabled: false`, `simple_max: null`.
- **FR-002**: When the surface is off, uncalibrated (`simple_max` null), the global System One switch is off, or no client is injected, every subtask MUST run its agent's full model and no tier request MUST be made.
- **FR-003**: When a tier request is made and the client skips, times out, raises, or returns a missing or malformed answer, the subtask MUST run the full model. The tier MUST never be the light model unless a valid judgment at or below the bar says so.
- **FR-004**: The regex `ComplexityEstimator`, its tests and every call to it MUST be deleted. No code path MAY fall back to it.

**Task at hand (user-pinned)**

- **FR-005**: The tier MUST be judged on the task the user is trying to get done, not on the latest message alone. The judgment MUST run after the turn's context is gathered (after `fetch_context` and `match_skills`) and before `capability_check`.
- **FR-006**: The judgment state MUST carry these named fields, each capped, absent when empty: the user's message (`task`); the recent conversation, wider than the routing hint (`conversation`); the resume recap or session summary when the session resumed (`recap`); the top retrieved memory items (`memory`); the active goal, workflow or invoked procedure in focus (`focus`); the matched skill's name and description (`skill`). It MUST NOT carry an agent description or tool list (amended 2026-10-16: the `agent` field added noise on the tuned set), full transcripts, memory bodies beyond the caps, skill bodies, or database rows (pinned rule 6).
- **FR-007**: The question instruction MUST tell the model to judge the task the user is trying to get done and to use the conversation and context to resolve what "it", "that plan", "go ahead" or "the other one" refers to. It MUST NOT carry the routing instruction "history and context are background only".

**Question shape**

- **FR-008**: The judgment MUST be one Noul, `needs_deep_reasoning`: will doing this task well need careful reasoning, weighing options, synthesis across sources, planning, nuanced personal judgment or several dependent steps. It MUST be sent alone, with one attempt (`max_attempts=1`).
- **FR-009**: The light model MUST be chosen only when the Noul is at or below `simple_max`; above it, the full model. An answer equal to the bar counts as at or below.
- **FR-010**: The routing request MUST no longer ask the complexity Score. `complexity_lookup_max` MUST be deleted from the routing surface, and `RoutingEnvelope` MUST no longer carry `complexity` or `complexity_source`.

**Coverage**

- **FR-011**: Routing (every router path and `decompose`) MUST assign each subtask its agent's full model. Only the tier step MAY change it, and only to that agent's `model_simple`.
- **FR-012**: The tier step MUST judge every turn whose envelope has exactly one subtask, is not compound and has no conductor hint, and whose agent declares a `model_simple` that differs from its full model after override resolution. Every other turn MUST keep the full model with no request.
- **FR-013**: Delegated specialists (`delegate_to_agent`) and the conductor's companion MUST be unchanged by this phase.

**Trace**

- **FR-014**: Each turn's message trace MUST carry a `tier` record: agent, tier (`simple` or `full`), decided by (`system_one`, `off`, `uncalibrated`, `skip`, `invalid_answer`, `no_simple_model`, `compound`), and the model that ran. The judgment row MUST be appended to `judgments` (never replacing routing or skill rows) with `consumed` true only when it decided the tier. The trace REST response, the `trace_update` frame and the trace panel's Routing section MUST show it.
- **FR-015**: The `routing_log` columns `complexity` and `model_selected` MUST be dropped in a migration on the ze-core `zc` chain, and the routing store MUST stop writing them.

**Calibration and acceptance**

- **FR-016**: The surface MAY be enabled only when, on the held-out set, for English and for Portuguese separately, at the frozen `simple_max`: (a) zero false downgrades (rows gold-labelled `full` judged light); (b) light-model recall of at least 0.5 (at least half the rows gold-labelled `simple` judged light); (c) skipped or invalid rows at most 10% of the language's rows. Otherwise the verdict is KEEP OFF. Precision, latency p50/p90 and per-agent counts are reported, not gating.
- **FR-017** (amended 2026-10-16): The bar MUST be chosen on the tuned set only. It MUST judge no tuned `full` row light, sit at least 0.15 below the lowest tuned `full` Noul, and keep tuned light-model recall at or above 0.8 per language; among such bars, prefer the larger margin. If no bar meets all three, there is none and the surface stays off. The frozen value, both margins and the run-to-run noise MUST be recorded. (Originally: the highest Noul value at which no tuned `full` row is judged light.) The bar MUST be frozen (written into the spec's research notes with the date) before the held-out run.
- **FR-018**: The tuned set and the held-out set MUST be separate files of multi-turn rows. Each row MUST carry the routed agent, a conversation (zero or more prior turns), optional recap, memory, focus and skill fixtures, the user's message, the gold tier and a one-line reason. Each set MUST cover EN and PT equally, all three tiered agents, both tiers, and anaphoric follow-ups in both directions ("ok go ahead with that plan" after a planning exchange → `full`; "ok thanks" or "and the other one?" after a lookup → `simple`).
- **FR-019**: The held-out set MUST be written by an author who has not seen the tuned set or the bar, from a written brief ([contracts/holdout-brief.md](./contracts/holdout-brief.md)), and committed before any live run. It MUST be scored once for the verdict; after that it is spent for this bar.
- **FR-020**: Enabling the surface MUST be a separate commit that sets `enabled: true` and the bar with a dated comment quoting the held-out figures. It MUST NOT be part of the implementation commits.
- **FR-021**: A `make calibrate-complexity` target MUST run the live calibration (costs credits) and an offline `--check-sets` mode MUST validate the files with no network call. Default tests MUST mock the client and never call a vendor.

### Key Entities

- **Tier**: `full` (the agent's declared `model`) or `simple` (its `model_simple`). Only agents that declare a distinct `model_simple` have a choice.
- **Tier judgment**: one Noul over the task state; consumed only when it decides the tier.
- **Task state**: the named, capped context fields of FR-006.
- **False downgrade**: a turn that needed the full model but ran the light one. The harm the acceptance rule caps at zero.
- **Light-model recall**: the share of turns that the light model would serve well that actually get it. The savings the rule requires.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the shipped config, 100% of turns run their agent's full model and 0 tier requests are made.
- **SC-002**: No code path picks a model tier from the message text alone; the regex classifier is gone.
- **SC-003**: For a planning exchange followed by "ok go ahead with that plan" (EN and PT), the tier judgment receives the earlier turns that define the plan.
- **SC-004**: Every skip, timeout, error or malformed answer results in the full model (0 exceptions in unit fixtures).
- **SC-005**: Compound and conductor turns make 0 tier requests and keep the full model.
- **SC-006**: Every turn's trace states which tier ran and why.
- **SC-007**: The surface is enabled only with a written held-out ENABLE for both languages: 0 false downgrades and at least half of light-eligible turns served by the light model.
- **SC-008**: 0 live vendor calls in default tests.

## Assumptions

- `typesafe/jev-1.13` stays the pinned model; a model change needs a new calibration.
- One extra System One request adds roughly 0.45–0.6 s to a tiered turn (7 batched requests in dev traces, timeout 2 s). It is paid only when the surface is on and the turn is tierable. The calibration run measures it on the full sets.
- The light model's faster first token partly offsets the request on light turns.
- The three tiered agents stay companion, research and goals; a new agent that declares `model_simple` joins automatically, but the calibration covers only these three.
- Portuguese rows use the same English instruction text, as in 163–172.

## Out of Scope

- Escalating from the light to the full model inside the agent loop (alternative C; recommended follow-up).
- Per-subtask tiers on compound and conductor turns (alternative D).
- Tiering delegated specialists, and the gap that `delegate_to_agent` ignores `models.overrides` (recorded as a follow-up).
- Goal and workflow executors outside the conversation graph.
- Changing which agents declare `model_simple` or which models they declare.
- A Haiku task-restating step (alternative B).

## Verbatim Constraints

- `ComplexityEstimator`
- `model_simple`
- `needs_deep_reasoning`
- `simple_max`
- `system_one.surfaces.complexity`
- `complexity_lookup_max`
- `RoutingEnvelope`
- `routing_log`
- `fetch_context`
- `match_skills`
- `capability_check`
- `max_attempts=1`
