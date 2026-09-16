# Research: Specialist Memory Constitution (Phase 149)

## 1. Second prompt builder vs shared `_build_system_prompt`

**Decision:** Do not add a specialist prompt assembler. Calendar, messenger, and news already pass `_AGENT_INSTRUCTIONS` into `BaseAgent._build_system_prompt`. Tests assert the 141 order on those three agents’ assembled strings (constitution marker, then a unique job snippet, then `BIOGRAPHY_HEADING` / `## Retrieved biography` when biography is present). Empty biography still starts with constitution + job.

**Rationale:** Spec edge case: agents that already use the shared builder must not grow a second one (Principle VIII dual door).

**Alternatives considered:** Copy `_build_system_prompt` into each plugin — rejected. Override `_build_system_prompt` to bury job after biography — that would undo 141.

## 2. Domain instruction rewrite vs constitution-only

**Decision:** Keep each agent’s operational job (ISO-8601 calendar times, messenger send/list rules, news store-grounding and freshness). Add the same memory-use family as companion 141: apply facts silently; do not announce “I remember that you…”; do not dump biography unsolicited; if the user asks what Ze knows, answer from context without claiming a write; do not claim `remember_fact` / `forget_fact` success because those tools are not on the catalog. Delete any leftover “chat about memory” wording that contradicts that family.

**Rationale:** Spec US3 / FR-002: one constitution family. Shared `MEMORY_CONSTITUTION` is already prefixed; specialist jobs still lag companion’s silent-use copy.

**Alternatives considered:** Constitution prefix only, leave jobs untouched — rejected; US3 independent test reads agent instructions. A specialist-only paragraph that still allows “I remember that you…” as style — rejected as a dual dialect.

## 3. Unearned remember-tool claims (FR-004 / US2)

**Decision:** Reuse Phase 143 `enforce_memory_confirmations` on calendar, messenger, and news **turn paths**. The function **stays** in `ze_personal.agents.companion.honesty` (144: claim dialect stays out of `ze_agents`). Calendar and messenger already depend on `ze-personal`. Add `ze-personal` to `ze-news` so news imports the same function (one door). Specialists apply it to model text before `AgentResult.response`. With no `remember_fact` / `forget_fact` tools, every success claim is unearned. **Do not** extend the gate to unsolicited biography recitation (“I remember that you like aisle seats”) — that is Phase 145 (already landed before 149).

**Rationale:** US2 independent test drives “I’ll remember that.” Prompt copy alone failed that class of lie on companion (143). News cannot import `ze_core`. Lifting dialect into `ze_agents` contradicts the 144 pin. Copying the regex into three plugins is a dual door.

**Alternatives considered:** Prompt-only FR-004 — fails US2. Copy the regex into three plugins — dual door. Lift into `ze_agents.memory_honesty` — rejected (144 dialects). Implement 145 recitation product as a separate specialist gate — out of spec.

## 4. Stream dual door

**Decision:** News already answers `stream` via `_grounded_loop` (same as `run`); gate there. Calendar and messenger currently complete `stream` with tool-free `_client.stream`. After this phase those streams MUST NOT deliver an ungated remember-success claim: collect the completion (or delegate to gated `run`) and apply `enforce_memory_confirmations` before the user-visible text is finished. Prefer a single gated string yield if that matches existing tests; do not add a parallel ungated dialect.

**Rationale:** Principle VIII. Companion already hard-cut its stream bypass in 143.

**Alternatives considered:** Gate `run` only — leaves stream as a second door. Full 145-style token buffering for recitation — not this spec.

## 5. Catalogs and Phase 142

**Decision:** Assert `remember_fact` and `forget_fact` are absent from `CalendarAgent.tools`, `MessengerAgent.tools`, and `NewsAgent.tools`. Do not add those tools. Silent use of retrieved facts as **context** for domain answers is allowed; blocking gated writes from constraint facts is Phase 144.

**Rationale:** FR-003, FR-006, roadmap item 149.

**Alternatives considered:** Add remember tools so specialists can earn confirmations — forbidden by 142 and this spec.

## 6. Scope of agents

**Decision:** Calendar event agent, messenger, news only. Reminders, prospecting, goals, workflows, research, finance stay unchanged unless they share an instruction module (they do not).

**Rationale:** Spec US3 scenario 2 and assumptions.

## 7. Imports

**Decision:** New specialist wiring imports `enforce_memory_confirmations` from `ze_personal.agents.companion.honesty`. Do not import `ze_core`. Do not mass-rewrite existing `ze_agents` imports on these agents in this phase.

**Rationale:** FR-005 / Principle III / 144 dialect pin. Hard-cutting every plugin `ze_agents` import is unrelated.

**Alternatives considered:** Force all three agent modules onto `from ze_sdk import BaseAgent` in this phase — larger than 149; skip.
