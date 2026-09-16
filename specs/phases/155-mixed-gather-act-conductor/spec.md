# Feature Specification: Mixed Gather+Act → Conductor

**Feature Branch**: `155-mixed-gather-act-conductor`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "155 Mixed gather+act → conductor: If decompose yields more than one specialist and the set is mixed gather+act (read/research/lookup plus write/send/create; research+messenger is the motivating pair; classify via intent families read vs create/update/delete/send, not a two-name list), rewrite to companion primary the same way 153 does for sequential. Independent multi-read still fan-out+synthesize. Single-domain stays the specialist. Do not split parallel capability gates. Do not stall/replan. Do not promote."

**Governed by**: [`specs/arch/companion-conductor-roadmap.md`](../../arch/companion-conductor-roadmap.md) phase 155, [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md), [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), sequential rewrite [`153-sequential-routing-hard-cut`](../153-sequential-routing-hard-cut/spec.md), fat ACI [`151-fat-delegate-aci`](../151-fat-delegate-aci/spec.md), per-delegate gate [`152-per-delegate-gate`](../152-per-delegate-gate/spec.md), observability [`154-conductor-observability-eval`](../154-conductor-observability-eval/spec.md). Plugin isolation: companion MUST NOT import calendar or messenger tools.

**Depends on**: 153 `apply_conductor_rewrite` (today only `is_sequential && len(subtasks)>1`). 151/152 so mixed conductor turns stay fat-briefed and per-invocation gated.

**Does not start**: 156 stall/replan outer loop; 157 promote to workflow/goal; per-subtask gate on independent parallel graph path; procedures (135–139); restoring `_execute_compound` sequential.

---

## Overview

After 153, conductor rewrite fires only when Haiku marks the envelope sequential. “Research latest X and send an email report to Y” is dependent gather-then-act. If Haiku sets sequential false, the graph still fans out research and messenger together: the email has no research, and strictest-wins may hold the whole turn.

This phase extends the same companion-primary rewrite 153 already uses: more than one specialist **and** a mixed gather+act intent set also becomes a conductor turn, even when sequential is false. Independent multi-read still fans out and synthesizes. A single specialist stays that specialist. Parallel graph capability remains strictest-wins (a later spec). No stall loop. No promote.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Research then mail is one conversation with Ze (Priority: P1)

The user asks to research a topic and send an email report. Decompose lists research (read) and messenger (create/send). Sequential may be false. The graph still rewrites to companion as primary with the original prompt. Companion researches via delegate, then briefs messenger with that output. The user hears one voice. Parallel gather of both specialists does not run.

**Why this priority**: This is the failure 153 left when Haiku under-marks dependence.

**Independent Test**: Envelope with two subtasks, `is_sequential=False`, research `read` + messenger `create` (or `send`) → companion primary, hint stored, `is_compound` false. Existing sequential multi-specialist fixtures still rewrite.

**Acceptance Scenarios**:

1. **Given** decompose yields research with a gather intent and messenger with an act intent and more than one specialist, **When** rewrite runs (sequential true or false), **Then** companion is the primary executed agent and the former subtasks are a non-executable hint.
2. **Given** that rewritten turn, **When** companion works, **Then** it may `delegate_to_agent` (151) so messenger sees research in `prior_outputs` / `inputs`; specialists do not take the mic.
3. **Given** the same mixed pair with `is_sequential=True`, **When** rewrite runs, **Then** behavior matches 153 (no second rewrite path that drops the hint).
4. **Given** this phase ships, **When** mixed gather+act would previously `asyncio.gather` research and messenger, **Then** that fan-out MUST NOT run for that envelope.

---

### User Story 2 - Independent reads still fan out; single-domain still specialist (Priority: P1)

Two independent lookups (news and calendar, both gather) still run in parallel and synthesize. “What’s on Tuesday?” still goes to calendar. Two independent acts with no gather (if Haiku lists them and sequential is false) stay on the existing parallel compound path — this phase does not invent a second classifier for write+write.

**Why this priority**: Conductor is for mixed gather+act and sequential dependence, not a swarm for every compound.

**Independent Test**: Compound all-gather, sequential false → no companion rewrite. One subtask → that specialist. Two act-only subtasks, sequential false → still compound (strictest-wins unchanged).

**Acceptance Scenarios**:

1. **Given** independent multi-read (`is_compound`, not sequential, every subtask gather), **When** rewrite runs, **Then** the envelope is unchanged and fan-out + synthesize still occurs.
2. **Given** a single-domain research, messenger, or calendar turn, **When** routed, **Then** that specialist remains primary even if the intent is an act.
3. **Given** two act-only specialists and sequential false, **When** rewrite runs, **Then** companion is not forced primary (parallel gates stay later).
4. **Given** speech-act one-shots, **When** companion is already primary as today, **Then** 151/146 still work; this rewrite does not steal specialist-only turns.

---

### User Story 3 - Intent families, not a two-name allowlist (Priority: P2)

Classification uses each subtask’s intent: gather vs act. Research+messenger is the motivating pair, but calendar read + messenger create, or news read + calendar create, also rewrite. The engine does not hardcode `{research, messenger}` as the only pair.

**Why this priority**: A name list rot as soon as another read agent exists.

**Independent Test**: Unit table: mixed intents → rewrite; all gather → no rewrite (unless sequential); unknown intent treated per Assumptions.

**Acceptance Scenarios**:

1. **Given** calendar `read` and messenger `create` (or `send`), **When** rewrite runs, **Then** companion is primary (same as research+messenger).
2. **Given** news `read` and research `read`, sequential false, **When** rewrite runs, **Then** companion is not forced primary.
3. **Given** a new specialist whose intent is `read` plus another whose intent is `delete`, **When** rewrite runs, **Then** mixed gather+act still fires without editing a two-agent list.

---

## Edge Cases

- Sequential true, mixed or not, more than one subtask: still rewrite (153 unchanged).
- Sequential true, one subtask: stay specialist (153 unchanged).
- Mixed intents but only one specialist (two subtasks same agent): **Assumption**: unique specialist names ≤ 1 is single-domain; do not rewrite unless 153’s sequential+`len>1` already would. Prefer unique agents for the mixed rule; sequential `len(subtasks)>1` stays 153’s bar even if the same agent appears twice.
- Haiku emits `send` while messenger’s declared key is `create`: treat `send` as act.
- Haiku emits `lookup` / `search`: treat as gather aliases of `read`.
- Unknown intent: not gather and not act; mixed requires at least one classified gather and one classified act.
- Empty intent string: same as unknown.
- Companion already primary from embed_route: rewrite is a no-op on identity; hint still recorded when mixed/sequential multi applies from decompose.
- Confirmation mid-sequence: 152 pause/resume; 155 must not restore parallel fan-out on resume.
- Plugin isolation: companion still only remember/forget/delegate.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When decompose yields **more than one specialist** and the subtask intents are **mixed gather+act**, the system MUST apply the same companion-primary rewrite 153 uses for sequential multi-specialist turns (`conductor_hint`, original user prompt, not compound), even if `is_sequential` is false.
- **FR-002**: Sequential multi-specialist rewrite (`is_sequential` and `len(subtasks)>1`) MUST keep working exactly as 153; this phase MUST NOT require sequential true for mixed gather+act.
- **FR-003**: Independent multi-read (all classified gather, sequential false) MUST keep graph fan-out + synthesize. Single-specialist envelopes MUST keep that specialist primary.
- **FR-004**: Gather vs act MUST be classified from subtask **intent** families, not a hardcoded two-agent name list. Gather includes `read` and aliases `lookup`, `search`. Act includes `create`, `update`, `delete`, `send`. Motivating pair remains research+messenger.
- **FR-005**: Graph parallel capability (strictest-wins on independent compound) MUST stay as today. This phase MUST NOT split per-subtask gates on the parallel path.
- **FR-006**: 151 fat `delegate_to_agent`, 152 per-delegate gates/`request_id`, and 154 trace/progress/eval contracts MUST remain. Mixed rewritten turns MUST be inspectable as conductor turns (hint + ledger), not fake parallel compound.
- **FR-007**: This phase MUST NOT implement stall/replan (156), promote to workflow/goal (157), procedure activation (135–139), swarm, or restore `_execute_compound` sequential.

### Key Entities

- **Gather intent**: A subtask intent in the read/lookup/search family.
- **Act intent**: A subtask intent in the create/update/delete/send family.
- **Mixed gather+act set**: At least one gather and at least one act among decompose subtasks, with more than one specialist.
- **Conductor rewrite**: 153 companion-primary envelope + hint; mixed is an additional predicate, not a second graph.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of tested mixed gather+act fixtures (including sequential false, research+messenger) execute companion as primary and 0% fan-out both specialists in one gather.
- **SC-002**: 100% of tested independent multi-read fixtures still synthesize without companion primary.
- **SC-003**: 100% of tested single-domain fixtures keep the specialist primary.
- **SC-004**: 100% of tested sequential multi-specialist fixtures still rewrite as in 153.
- **SC-005**: Classification tests pass for calendar-read+messenger-act and fail to rewrite all-read pairs without using an agent-name allowlist of size two.

---

## Assumptions

- “More than one specialist” for the **mixed** rule means more than one distinct agent name. Sequential rewrite still uses `len(subtasks)>1` as in 153.
- `manage` (workflow) is **not** in the act family this phase unless listed as `create`/`update`/`delete`/`send`; mixed workflow+research without those intents stays Haiku’s sequential bit. Informed default: do not treat `manage` or `reason` as gather or act.
- Haiku `intent` strings are compared case-insensitively after strip.
- 156/157 remain unspecified product work; 155 only routes mixed turns to the existing conductor.
- Eval may add one mixed sequential-false scenario; 154’s four ids stay valid.

## Out of Scope

- Stall / Magentic outer loop (156).
- Promote this instance to workflow/goal (157).
- Per-subtask capability on independent parallel fan-out.
- Procedures / `memory_procedures` / 135–139.
- Feeding prior outputs inside deleted `_execute_compound` sequential.
- Swarm / specialist-as-speaker.

## Verbatim Constraints

- `apply_conductor_rewrite`
- `is_sequential`
- `delegate_to_agent`
- `prior_outputs`
- `inputs`
- `conductor_hint`
- `conductor_ledger`
- `read`
- `create`
- `update`
- `delete`
- `send`
- Principle VIII

## After this feature / Future work

156 stall/replan (Ready to implement; depends on this rewrite). 157 promote (Ready to implement; depends on 156). Later: parallel per-subtask gates.
