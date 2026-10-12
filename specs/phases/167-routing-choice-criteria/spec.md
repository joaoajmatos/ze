# Feature Specification: Routing Choice Criteria

**Feature Branch**: `164-research-routing` (floor branch; no `167-*` branch is created)

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: "Make the 164 routing Choice safe to enable. Live recalibration 2026-10-12 (k=5): 0.957 on the tuned set, 0.70 EN / 0.80 PT on the held-out set, ECE 0.27. Every held-out miss is an explain / compare / how-to research question sent to companion."

**Governed by**: [`specs/arch/system-one-models.md`](../../arch/system-one-models.md) O2, [`specs/arch/companion-conductor-roadmap.md`](../../arch/companion-conductor-roadmap.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md).

**Depends on**: Phase [164](../164-routing-choice-after-e5/spec.md) Implemented. Phase [166](../166-skill-suggestion-system-one/spec.md) merged (shares the calibration pattern).

**Does not**: change phases 153/155, the conductor, `decompose`, E5 encoding, the 160 cosine bars, or skills.

---

## Overview

Phase 164 ships the routing Choice off. It cannot be enabled: on a held-out set it is about 0.98 confident while 80% right. The research (floor note "164 Research Scope") found three causes:

1. **Contradictory descriptions.** The companion and research `@agent` descriptions both claim "explain X". The Choice uses descriptions as its criteria, so companion is a description-approved answer for explanations. Companion cannot search the web and has no rule to delegate facts, so the likely outcome is an unsearched answer.
2. **Bare Choice wording.** The question is "which one agent"; the `none` criterion is one weak sentence.
3. **A weak shortlist.** E5 cosines on this roster are flat (0.76–0.82, gaps 0.00–0.03). On a fresh set the gold agent is outside the top 6 for 43% of rows (offline recall at k=5/6/7/8/9/10 = 0.571 / 0.571 / 0.714 / 0.714 / 1.0 / 1.0). No Choice wording can pick an agent it is never offered.

This phase fixes the three causes and then re-measures against two held-out sets. If no `choice_trust` meets the bar, the phase closes with the surface off and says so (option F).

## Clarifications

### Session 2026-10-12

- Q: Who owns explain / compare / how-to questions? → A: Research. The gold stays as written. Companion keeps chat, emotion, reasoning about the user's own situation and multi-specialist conducting. The contradictory "explain X" is removed from companion's description in this phase.
- Q: Which lever first? → A: Lever C: Choice-specific use-for / not-for criteria and instructions, plus a stronger `none` criterion. The shortlist size is the second lever, used only if C alone misses the bar. Where the criteria live is decided in this spec (see FR-003).
- Q: Fresh data and a live companion check? → A: Yes to both. The spec author wrote `eval/calibration/routing_holdout2.jsonl` (30 EN+PT rows) independently of the implementer; it is never tuned against. The implementer prepares a small live companion check script; the user runs it (it costs credits).
- Q: Acceptance rule? → A: At least 0.95 routing accuracy for EN and PT on both held-out sets, ECE at most 0.10, zero research→companion misses. If no `choice_trust` meets it after lever C and the shortlist sweep, close as option F: the surface stays off and the docs say why.
- Q: Deviation from "k=6" — **needs user confirmation.** The user named `shortlist_k: 6` as the second lever. Offline recall on the fresh set is 0.571 at k=6, so k=6 cannot reach the bar. This spec makes an offline recall gate the first task and sweeps k from 6 up to the roster size, adopting the smallest k with recall ≥ 0.95 on all three sets. If that k is the whole roster, E5 no longer filters for the Choice (it keeps the 160 cosine skip path). The user may veto this and ask for option F instead.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An explanation question reaches research (Priority: P1)

The user asks "explain how DNS resolution works", "compare Notion and Obsidian", "how do I set up a cron job" or "who won the last Champions League final". The router sends it to the research agent, which searches the web. Companion does not answer from memory.

**Why this priority**: This is the whole failure. Every held-out miss was this shape.

**Independent Test**: With a fake System One client, a research-shaped prompt and a roster that includes companion, the criteria passed to the Choice make research the only agent whose criteria cover the request. In the live calibration, research rows score ≥ 0.95 and none go to companion.

**Acceptance Scenarios**:

1. **Given** the companion description, **When** it is read, **Then** it does not list "explain X" or any web-fact use.
2. **Given** a research prompt in EN or PT, **When** the Choice runs on the calibrated surface, **Then** it picks research, never companion.
3. **Given** a prompt about the user's own situation ("I'm torn between my job and a startup"), **When** the Choice runs, **Then** companion is chosen, not research.

---

### User Story 2 - The Choice is offered the right agents (Priority: P1)

The gold agent is in front of the Choice for at least 95% of rows on every calibration set, not only the tuned one.

**Why this priority**: A wrong shortlist caps accuracy no matter how good the wording is.

**Independent Test**: The offline recall command reports ≥ 0.95 at the chosen `shortlist_k` on `routing.jsonl`, `routing_holdout.jsonl` and `routing_holdout2.jsonl`. It costs nothing.

**Acceptance Scenarios**:

1. **Given** the three sets, **When** recall is swept from k=6 to the roster size, **Then** the smallest k with recall ≥ 0.95 on all three is recorded in the spec's research notes and set in config.
2. **Given** that k equals the roster size, **When** the router builds the Choice, **Then** the docs state that E5 no longer filters for the Choice and still drives the 160 skip path.
3. **Given** no k reaches the bar, **When** the gate runs, **Then** the phase closes as option F before any live spend.

---

### User Story 3 - The surface is enabled only if it earns it (Priority: P1)

A `choice_trust` and `multi_specialist_hold` are chosen from live calibration and the surface is enabled, or the phase closes with the surface off and documented.

**Why this priority**: The 164 failure was shipping a bar the held-out data did not support.

**Independent Test**: The calibration script run on both held-out sets reports accuracy ≥ 0.95 EN and PT per set, ECE ≤ 0.10, zero research→companion misses at the chosen bar. If any fails for every bar, `config.yaml` keeps `enabled: false` with a dated note.

**Acceptance Scenarios**:

1. **Given** a bar meeting the rule on both sets, **When** the config is written, **Then** `enabled: true` with the bars and a dated comment.
2. **Given** no bar meets the rule, **When** the phase closes, **Then** the surface stays off, null bars stay null, and the 164 spec status note and docs state "calibrated, not enabled" with the figures.

---

### User Story 4 - We learn what companion does with a research question (Priority: P2)

A small live script runs the 6 research prompts of `routing_holdout.jsonl` through companion and reports whether it delegates to research, the cost, the latency and whether the answer cites sources. The user runs it.

**Why this priority**: It informs a later decision on whether companion could be a front door. It does not gate enabling.

**Independent Test**: The script exists, is opt-in, prints a table, and refuses to run without an explicit flag. The default test suite never calls it.

**Acceptance Scenarios**:

1. **Given** the script and credits, **When** the user runs it, **Then** it prints per prompt: delegated yes/no, LLM call count, cost, wall time, cited sources yes/no.
2. **Given** no flag, **When** it is invoked, **Then** it exits with a message and makes no network call.

---

## Edge Cases

- A new plugin agent without `routing_criteria`: the Choice falls back to its `description` (no breakage).
- Roster shorter than `shortlist_k`: the whole roster is offered (existing clamp).
- Mixed prompts ("research X and remind me"): the multi-specialist Noul and `none` still send them to decompose; the new wording must not turn them into a single-agent trust.
- PT prompts: criteria are English text; PT rows must score the same as EN (the bar applies per language).
- Calibration sets are never edited to fit the surface; changing a gold label needs a user decision.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Companion's `@agent` description MUST NOT claim explanation, comparison, how-to or web-fact questions. It MUST keep chat, emotion, reasoning about the user's own situation and multi-specialist conducting. Research's description MUST keep claiming them.
- **FR-002**: The Choice instructions MUST tell the model to prefer the agent that can search the web or use tools over an agent that would answer from its own knowledge, when the request needs facts, comparisons, recent information or step-by-step help. The instruction text MUST NOT name any plugin agent.
- **FR-003**: Each agent MAY declare an optional `routing_criteria` class attribute (use-for / not-for text) on `BaseAgent` in `ze_agents`. `build_questions` MUST use it as the Choice criterion for that agent and fall back to `description` when absent. `ze_core` MUST NOT hard-code any plugin agent name. The registry MUST NOT require the field. E5 passage text MUST stay the `description` (the experiments show description edits do not help E5).
- **FR-004**: The `none` criterion MUST say that `none` is correct when no listed agent can do the job alone, when the request is for something Ze has no capability for (for example home-device control), or when it needs more than one listed agent. The wording MUST include examples that name no agent.
- **FR-005**: The `routing_criteria` for companion and research MUST state their lanes in "use for / not for" form, with companion's text saying that questions needing facts from the web go to research even when companion could answer from memory.
- **FR-006**: `shortlist_k` MUST be chosen by an offline recall sweep from 6 up to the roster size: the smallest k with recall ≥ 0.95 on `routing.jsonl`, `routing_holdout.jsonl` and `routing_holdout2.jsonl`. The recall command MUST accept k up to the roster size and all three sets MUST be reported in one run.
- **FR-007**: If no k up to the roster size reaches recall ≥ 0.95 on all three sets, the phase MUST close as option F before any live run.
- **FR-008**: The live calibration MUST be run by the user, not the implementer, on `routing_holdout.jsonl` and `routing_holdout2.jsonl`. The implementer prepares the command and the report. The report MUST print per-set, per-language accuracy, ECE, and a research→companion miss count for each candidate `choice_trust`.
- **FR-009**: The surface MAY be enabled only when, at the chosen `choice_trust`, both held-out sets have EN and PT accuracy ≥ 0.95, ECE ≤ 0.10 and zero research→companion misses. Otherwise `enabled: false`, bars stay `null` and the docs say "calibrated, not enabled" (option F).
- **FR-010**: `routing_holdout2.jsonl` MUST NOT be used to tune criteria text or the shortlist. It is a check set. Criteria are tuned against `routing.jsonl` only; `routing_holdout.jsonl` is already used for diagnosis and counts as a check set for acceptance, not for tuning beyond the failure described here.
- **FR-011**: An opt-in script MUST run the 6 research prompts of `routing_holdout.jsonl` through the real companion and report: delegated to research (yes/no), LLM call count, cost, wall time, cited sources. It MUST NOT run in the default test suite.
- **FR-012**: Default tests MUST mock the judgment client and never call a vendor.
- **FR-013**: Phases 153/155, `decompose`, the conductor rewrite and the 160 cosine bars MUST NOT change. On skip, behavior MUST match 164 exactly.
- **FR-014**: The Choice question text and criteria MUST be recorded on the trace judgments as they are today (no new trace field).

### Key Entities

- **Routing criteria**: Per-agent use-for / not-for text the Choice sees. Optional; defaults to the description.
- **Shortlist k**: How many E5-ranked agents the Choice is offered. Chosen by recall, not by taste.
- **Held-out check sets**: `routing_holdout.jsonl` (22 rows) and `routing_holdout2.jsonl` (30 rows, EN+PT). Never tuned against.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Offline gold-agent recall at the chosen k is ≥ 0.95 on all three calibration sets.
- **SC-002**: At the chosen `choice_trust`, routing accuracy is ≥ 0.95 for EN and for PT on `routing_holdout.jsonl` and on `routing_holdout2.jsonl`, with ECE ≤ 0.10.
- **SC-003**: Zero research-gold rows are routed to companion on either held-out set.
- **SC-004**: If SC-001 or SC-002 cannot be met, the phase closes with the surface off and the docs state the measured figures (option F). No threshold is lowered to fit.
- **SC-005**: With the surface off or skipped, routing unit fixtures show 0 differences against 164.
- **SC-006**: 0 live vendor calls in default tests.
- **SC-007**: The companion live check produces a table for all 6 prompts when the user runs it.

## Assumptions

- The roster is the 10 agents enabled on the calibration roster today (`calendar, companion, goals, ingestion, loops, messenger, prospecting, reminders, research, workflow`).
- `routing_holdout2.jsonl` gold labels follow the same rules as `routing_holdout.jsonl` (mixed prompts carry `gold_multi: true` with the gathering agent as gold).
- With only 10 agents, offering the whole roster to the Choice is affordable (prompt tokens only; still one request, one attempt).
- Typesafe Jev accuracy on the new wording is unknown until the user runs the live calibration.

## Out of Scope

- Making companion the front door for factual questions (option E). The live check informs it; it is not decided here.
- Changing E5 descriptions for recall, or a new embedding model.
- Deleting Haiku decompose; changing conductor caps or rewrite.
- Skills gating (166) and speech-act (163).
- Relabeling gold to accept companion on research prompts (option D).

## Verbatim Constraints

- `EmbeddingRouter`
- `choice_trust`
- `multi_specialist_hold`
- `shortlist_k`
- `routing_criteria`
- `build_questions`
- `none`
- `routing_holdout2.jsonl`
