# Research: Speech-Act Routing (Phase 142)

## 1. Where the classifier lives

**Decision:** Extend Phase 140’s extractor JSON to return `speech_act` plus optional `facts[]`. One LLM call. In-turn routing is companion tools + `delegate_to_agent` (already used by research). Post-turn extraction cannot admit facts when `speech_act` is reminder/loop/goal/ingest/drop/commitment.

**Rationale:** Spec wants extractor to stop eating commitments even if companion mis-routes. Combining calls keeps cost down.

**Alternatives considered:** Separate classifier node in the graph — more orchestration, Phase 005 graph change out of proportion. Clone `set_reminder` onto companion — duplicates calendar plugin tools, violates FR-004 spirit. Router-only (embedding intents) — “remember to call Tuesday” will keep hitting companion.

## 2. Companion vs reminders agent

**Decision:** Update companion `description` so timed remember is allowed to **hand off** to the reminders agent via `delegate_to_agent`. Do not put `set_reminder` on companion’s tool list this phase (FR-004: don’t expand specialist catalogs; don’t fork reminder tools).

**Alternatives considered:** Always re-route the whole graph — harder mid-turn. Give companion reminder tools — simpler UX, but duplicates ISO-8601 reminder implementation and pulls `ReminderStore` into personal.

## 3. Product defaults (table)

Pinned in spec; not re-litigated:

- Time trigger beats biography fact.
- Appointment without “put on calendar” → reminder, not calendar event.
- Vague self-improvement → loop unless milestones/timeframe → goal.
- Constraint stored as fact; no send veto (P5).

## 4. Dual-write prevention

**Decision:** Classifier emits one primary `speech_act`. Extractor emits facts iff primary is `fact` (R1/R9). Tests assert not both reminder created and fact row for R3/R8/R11.

## 5. Dependency

**Decision:** Implement after Phase 140. Phase 141 optional but companion copy should not fight routing (no “always remember as a fact”).
