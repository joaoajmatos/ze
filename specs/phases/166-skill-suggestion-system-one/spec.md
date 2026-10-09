# Feature Specification: System One Skill Gating

**Feature Branch**: `166-skill-suggestion-system-one`

**Created**: 2026-10-09

**Status**: Draft

**Input**: User description: "O3 from the System One roadmap: after the E5 shortlist, a typed System One Choice picks at most one skill for automatic application and a Noul gates it. Keep `/skill-name` in code. Off by default with null bars, EN+PT calibration set, shortlist size chosen from data. No suggestion UX."

**Governed by**: [`specs/arch/system-one-models.md`](../../arch/system-one-models.md) O3, [`specs/arch/local-embeddings.md`](../../arch/local-embeddings.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md). Phases [114](../114-agent-skills/spec.md), [162](../162-system-one-client/spec.md), [163](../163-speech-act-system-one/spec.md), [164](../164-routing-choice-after-e5/spec.md).

**Depends on**: Phase 162 Implemented (client, DI, trace judgments). Phase 114 Implemented (skills, matching, tool narrowing). Phases 163 and 164 are Implemented but uncalibrated; their patterns are reused, not their bars.

**Does not start**: A suggestion UX (asking the user to approve a skill before it applies); loop extraction (O4); any change to `/skill-name` invocation, skill review, `allowed-tools` intersection, or workspace scripts.

**Naming note**: The roadmap calls this "skill suggestion". Nothing is suggested to the user: matched skills are applied and disclosed after the fact (114 FR-011). This phase **gates automatic application**. The directory keeps the roadmap name; the title says what it does.

---

## Overview

Phase 114 applies a skill automatically when the E5 cosine between the message and the skill's `name: description` is at least `skills.match_threshold` (0.5). Cosine is similarity, not a decision. Two near-miss descriptions both clear the floor and both inject their instructions. A paraphrase that matters scores 0.46 and never applies. Every applied skill also narrows the agent's tools, so a wrong match has a cost.

This phase keeps E5 as the **shortlist** and adds a typed judgment after it. One batched System One request asks which single shortlisted skill fits (a Choice that includes `none`) and whether the request needs a skill at all (a Noul). Pure code turns the answers into apply, drop, abstain or skip. Explicit `/skill-name` stays in code and bypasses the judgment. With the surface off, uncalibrated or skipped, the 114 path runs unchanged.

## Clarifications

### Session 2026-10-09

- Q: What does the judgment control? → A: It only gates or demotes **automatic** matches. Explicit `/skill-name` never goes through it. The shortlist uses a lower, shortlist-only pre-floor (`shortlist_floor`, near 0.35) so a skill that scores just under `match_threshold` can be a candidate. A skill may therefore be applied below 0.5, and only when the Choice and the Noul both clear their calibrated bars. Any apply below `match_threshold` MUST be identifiable on the message trace. Nothing below the pre-floor is ever applied.
- Q: How many skills apply per turn? → A: At most **one** automatic skill: the Choice picks one winner and the Noul gates it. Explicit `/skill-name` skills still stack on top, as in 114. This is a deliberate narrowing of 114 ("all matched skills used for that turn are surfaced", edge case in 114 and FR-019). 114 docs and spec text change to say so; on skip, the 114 behavior (every skill at or above the floor applies) is unchanged.
- Q: What text does the judgment see, and what text is embedded? → A: The state is the 164 `build_state` shape (user text, short history hint, routing hints), capped. The shortlist is embedded from the raw prompt (the matcher's existing `encode_query`). Reusing the router's query vector is evaluated in the plan and used only if it embeds the same text; the router embeds the prompt plus history and hints, so the likely outcome is that the matcher keeps its own single encode. This resolves the 114 FR-019 drift ("existing routing embedding" versus a second encode) by naming what is actually embedded.
- Q: Is there a suggestion UX? → A: No. 166 gates auto-application only. An "ask before applying" flow is a later phase and would need the confirm protocol settled first.
- Q: Ship state, calibration and shortlist size? → A: Surface off with `null` bars, same as 163 and 164. An EN+PT labeled set of about 80 rows ships with `make calibrate-skills`. `shortlist_k` is a **config value with no hard-coded default decision**: the calibration reports shortlist recall of the gold skill at k = 3 through 8 beside Choice accuracy, and a task picks the default from that report. The pick is informed by the 164 tuning findings: gold agents missed the top-4 shortlist in the first live run (recall 0.826 at k=4, 0.870 at k=5); a sharper description lifted recall to 0.870 at k=4 and 0.957 at k=5, and 164 now defaults to 5. Description quality drives E5 recall, so the calibration roster uses realistic descriptions.
- Q: `AgentState.judgments`? → A: Append-only for this phase. `match_skills` reads the rows `embed_route` wrote and appends its own; it never replaces them.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Only the skill that fits applies (Priority: P1)

The user has two active skills with similar descriptions, for example an email-tone skill and a meeting-notes skill. A message is clearly about one. Today both can clear 0.5 and both inject instructions and narrow tools. With the surface calibrated, the Choice names the right one, the Noul says a skill is needed, and only that skill applies.

**Why this priority**: Wrong or doubled skills are the cost the judgment exists to remove.

**Independent Test**: Two active skills both above `match_threshold`; fake Choice names skill A at high peakedness and the Noul is above its bar. Only A is in `active_skills` and `skills_used`. `allowed-tools` is computed from A alone.

**Acceptance Scenarios**:

1. **Given** two skills at or above 0.5 and a trusted Choice for A, **When** `match_skills` runs, **Then** only A applies and its trace row records trigger `automatic` and its similarity.
2. **Given** a Choice of `none`, **When** `match_skills` runs, **Then** no automatic skill applies even if some skill scored above 0.5.
3. **Given** the Noul below its bar, **When** a Choice named a skill, **Then** no automatic skill applies.
4. **Given** a message with `/skill-name` and a trusted Choice for a different skill, **When** `match_skills` runs, **Then** both apply (explicit stacks), and the `allowed-tools` restriction is the intersection of both.

---

### User Story 2 - A skill just under the floor can still apply, visibly (Priority: P1)

A paraphrased request scores 0.43 against the right skill, below `match_threshold`, above `shortlist_floor`. The Choice names it with high peakedness and the Noul clears its bar. The skill applies, and the message trace shows that it applied below the floor.

**Why this priority**: This is the recall win of the phase. It is also the riskiest behavior, so it must be inspectable.

**Independent Test**: One active skill at similarity 0.43; fake Choice returns it at high peakedness; fake Noul above the bar. The skill is in `skills_used`, marked as applied below the floor, and the `skill` judgment row is `consumed`.

**Acceptance Scenarios**:

1. **Given** a skill between `shortlist_floor` and `match_threshold`, **When** the Choice and Noul both clear their bars, **Then** it applies and the trace identifies the below-floor apply.
2. **Given** the same skill and a Choice that is unsure or `none`, **When** `match_skills` runs, **Then** it does not apply.
3. **Given** a skill below `shortlist_floor`, **When** any judgment answer arrives, **Then** it is not in the shortlist and never applies.

---

### User Story 3 - Off, unsure and failing paths keep today's behavior (Priority: P1)

The surface ships off with null bars. When the surface is disabled, uncalibrated, the client skips, an answer is invalid, or the Choice is unsure, the 114 path runs exactly as today: every active skill at or above `match_threshold` applies, and `/slug` stacks.

**Why this priority**: No regression on the default build, and no new failure mode when the vendor is down.

**Independent Test**: Run the 114 matcher fixtures with the surface off, with a client that skips, and with a client that returns an invalid answer. Results are identical to the 114 results.

**Acceptance Scenarios**:

1. **Given** `system_one.surfaces.skills.enabled` is false, **When** `match_skills` runs, **Then** no System One request is made and the result equals the 114 result.
2. **Given** enabled with a `null` bar, **When** `match_skills` runs, **Then** no request is made, a warning is logged once per match call, and the result equals the 114 result.
3. **Given** a client skip (timeout, overload, missing key), **When** `match_skills` runs, **Then** the 114 result applies and the trace carries skip rows with the skip reason.
4. **Given** an unsure Choice (peakedness below `choice_trust`), **When** `match_skills` runs, **Then** the 114 result applies (abstain) and the judgment rows are not `consumed`.

---

### User Story 4 - Calibration produces the bars and the shortlist size (Priority: P2)

A maintainer runs `make calibrate-skills`. The report shows Choice accuracy, `none` precision and recall, Noul separation, a reliability table, and the shortlist recall of the gold skill at k = 3 through 8. An offline mode prints the recall table with no System One call and no credits. The maintainer sets `choice_trust`, `needs_skill_hold` and `shortlist_k` from it.

**Why this priority**: Without bars the surface stays off. Without recall data `shortlist_k` repeats the 164 mistake (a gold item outside the shortlist).

**Independent Test**: The script loads the labeled set against the fixed roster, builds the production shortlist with the real E5 singleton, and prints the tables. The offline mode runs without network. Pytest never collects the live path.

**Acceptance Scenarios**:

1. **Given** the labeled set and roster, **When** the offline recall mode runs, **Then** it prints recall at k = 3 through 8 for the gold skill, per language, using the same shortlist helper as production.
2. **Given** a live run, **When** it finishes, **Then** it prints suggested values for `choice_trust` and `needs_skill_hold` and the k with the smallest shortlist that reaches the target recall.
3. **Given** default CI, **When** the suite runs, **Then** no System One request is made.

---

### Edge Cases

- No active skills, or none at or above `shortlist_floor`: no System One request; result equals 114 (nothing at or above 0.5 exists either).
- One shortlisted skill: still a Choice over that skill plus `none`; the shortlist does not need two entries.
- A shortlist larger than the number of active skills simply includes all of them above the floor; `shortlist_k` is an upper bound.
- Explicit slugs that matched are removed from the candidate set before the shortlist; if nothing remains, no request is made.
- Two skills with the same slug (bundled and imported, 114 FR-017): Choice keys must be unique and stable; collisions are disambiguated by source in the key, and the answer maps back to exactly one skill.
- Empty or whitespace message, or an image turn with no caption: no request, as in 114.
- Skill descriptions are the Choice criteria. They are capped; a description longer than the cap is truncated for the request only, never in the store.
- A skill disabled, removed or sent back to review between shortlist and apply: the matcher reads active skills once per call; no second read.
- Compound turns: skills are matched once per turn on the original prompt, as today.
- `allowed-tools` narrowing is computed over the final applied set only; a dropped skill imposes no restriction.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: E5 encoding and the per-skill `name: description` passage embeddings MUST stay as in 114. System One MUST see only a shortlist of active, non-explicit skills at or above `shortlist_floor`, capped at `shortlist_k`, plus `none`.
- **FR-002**: When the surface is enabled and calibrated, one batched request with `max_attempts=1` MUST carry two questions: a Choice over the shortlist plus `none` ("which one skill fits?") and a Noul `needs_skill`. Option keys are skill identifiers; criteria are the skill descriptions.
- **FR-003**: Pure code MUST decide the outcome. **Apply**: Choice names a shortlisted skill at peakedness at or above `choice_trust` AND the Noul is at or above `needs_skill_hold`. **Abstain**: Choice peakedness below `choice_trust`, whatever the label; the 114 result applies. **Drop**: Choice is `none` at or above `choice_trust`, or the Noul is below its bar; no automatic skill applies. **Skip**: surface off, a null bar, client skip, invalid answer; the 114 result applies.
- **FR-004**: At most one automatic skill MUST apply per turn when a judgment is consumed. Explicit `/skill-name` skills MUST still apply and stack; they never pass through the judgment. On abstain or skip, 114 behavior (all skills at or above `match_threshold`) is unchanged.
- **FR-005**: A skill with similarity below `match_threshold` and at or above `shortlist_floor` MAY apply only through an Apply outcome. A skill below `shortlist_floor` MUST NOT apply through any path except explicit invocation.
- **FR-006**: The message trace MUST make a below-`match_threshold` apply identifiable, in addition to recording similarity. `skills_used` rows for trigger `automatic` keep their fields; the trace panel MUST show the below-floor mark.
- **FR-007**: `/skill-name` parsing, resolution, the review gate, `allowed-tools` intersection (FR-008 of 114), instruction injection and workspace script approval MUST NOT change.
- **FR-008**: The judgment state MUST be the 164 shape: the user text, a short history hint when present, and the routing hints when present, each capped. No `AgentState` dump, no skill instruction bodies; only skill names and descriptions go in as criteria.
- **FR-009**: `match_skills` MUST append its judgment rows to `state["judgments"]` without replacing the rows `embed_route` wrote. `consumed` is true only for the questions that decided the outcome. Skip rows carry `kind` from the question definition and the skip reason.
- **FR-010**: Surface config MUST live at `system_one.surfaces.skills` with `enabled`, `choice_trust`, `needs_skill_hold`, `shortlist_k` and `shortlist_floor`. Bars are `null` until calibrated; enabled with a null bar means skip with a warning log. Invalid values (NaN, out of range, wrong type) become `null`/default with a warning. A `shortlist_floor` above `match_threshold` is clamped to it with a warning. Cookbook numbers MUST NOT ship.
- **FR-011**: `shortlist_k` MUST be a config value. Its shipped default MUST be chosen from the calibration recall report (k = 3 through 8) and recorded in the spec's tuning note, not assumed. `shortlist_floor` defaults near 0.35 and MUST be validated by the same report.
- **FR-012**: The matcher MUST embed the message once per call. Reuse of the router's query vector is allowed only if it embeds the same text as the matcher needs; otherwise the matcher keeps its own encode.
- **FR-013**: Fail open: any exception from the client, a malformed answer, or a Choice key outside the shortlist MUST yield the 114 result and a skip row. The turn never fails because of this surface.
- **FR-014**: Default tests MUST mock the client. Default `make test` MUST NOT call OpenRouter System One.
- **FR-015**: `eval/calibration/skills.jsonl` MUST hold about 80 labeled EN+PT rows (applies, near-miss between similar skills, no-skill turns, below-floor paraphrases, explicit `/slug`) against a fixed roster fixture. `make calibrate-skills` MUST report Choice accuracy, `none` precision and recall, Noul separation, a reliability table, shortlist recall at k = 3 through 8, a bar grid, and suggested values. Option order is shuffled in eval only. An offline recall-only mode MUST need no credits.
- **FR-016**: Public docs MUST describe the narrowing from "all matched skills" to "one automatic skill plus explicit skills" when the surface is on, and the unchanged 114 behavior when it is off.
- **FR-017**: This phase MUST NOT change speech-act admission (163), routing (164), capability modes, the confirm protocol, or skill import and review.

### Key Entities

- **Skill shortlist**: Active, non-explicit skills at or above `shortlist_floor`, ranked by cosine, at most `shortlist_k`.
- **Skills judgment**: The batched Choice (`skill`) and Noul (`needs_skill`) with their decision outcome.
- **Below-floor apply**: An automatic skill applied with similarity under `match_threshold` through an Apply outcome.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the surface off, uncalibrated, skipped or invalid, 0 differences from the 114 matcher fixtures (100% of existing matcher and node tests pass unchanged).
- **SC-002**: With a trusted Choice, a fixture with two skills above 0.5 applies exactly one automatic skill, and an explicit `/slug` still stacks.
- **SC-003**: A fixture with a skill between `shortlist_floor` and `match_threshold` applies it on Apply, and the trace shows the below-floor mark. The same fixture applies nothing on `none`.
- **SC-004**: The calibration set has at least 80 rows with at least 30% Portuguese, and the offline recall mode prints recall at k = 3 through 8 with no network call.
- **SC-005**: 0 live vendor calls in default tests.
- **SC-006**: `AgentState.judgments` after `match_skills` still contains every row written by `embed_route` in the same turn.

---

## Assumptions

- 162 Implemented. The OpenRouter System One client, DI and trace judgments already exist.
- `shortlist_floor` and the shipped `shortlist_k` are measured, not assumed; 0.35 and the 164 value of 5 are starting points only.
- Bars ship `null`. A first live run may find no safe bar, as happened for routing; the surface then stays off.
- The calibration roster is synthetic and fixed, because real skills vary per user. It uses realistic, distinguishable descriptions, since description quality drives E5 recall.
- Skill counts are small (a handful to a few dozen). Latency is one request per turn that has a non-empty shortlist.

## Out of Scope

- A suggestion or approval UX for skills.
- Choosing among several skills per turn, or per-skill Nouls.
- Changing the E5 model, the per-skill embedding cache, or `match_threshold` semantics on the 114 path.
- Skill import, review, recheck, scripts and workspace.
- Loop extraction (O4), retrieval classify (O5), push (O6).

## Verbatim Constraints

- `SkillMatcher`
- `match_skills`
- `match_threshold`
- `shortlist_floor`
- `shortlist_k`
- `needs_skill`
- `SystemOneClient`
- `skills_used`
- `allowed-tools`
- `/skill-name`
