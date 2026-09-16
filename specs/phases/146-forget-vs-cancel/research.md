# Research: Forget vs Cancel Across Stores

**Feature**: `146-forget-vs-cancel`  
**Date**: 2026-09-16

## 1. Where the miss actually lies

**Decision:** Treat R14 as two cooperating gates, not a new store. (1) Post-turn extractor: cancel/drop/abandon language aimed at a reminder, loop, or goal is `speech_act` `reminder` / `loop` / `goal`, never `forget`. `forget` remains biography retract (R2). (2) In-turn companion: explicit R14 instructions — delegate to `reminders`, `loops`, or `goals`; do not call `forget_fact` for that utterance. Post-turn extraction still cannot admit facts for those acts (already true when the act is not `fact`).

**Rationale:** Phase 142 wrote R14 in the table and told companion not to use `forget_fact` to cancel reminders. The extractor still lists `forget` as a speech act keyed off the verb “forget,” so “forget the dentist” classifies as biography forget. Companion tools still include `forget_fact` and the 143 precision ladder can miss (good) or, if a dentist-shaped fact exists, retract the wrong store. The remaining honesty gap is acting on the wrong store, then possibly claiming “I forgot.”

**Alternatives considered:**
- Prompt-only companion paragraph — 142 already has “Do not use this to cancel reminders…”; this spec exists because that is not enough.
- Hard speech-act classifier (non-LLM) — roadmap 148 follow-on; out of this phase.
- Graph router always sending “forget *” to reminders — steals R2 (“Forget that I like aisle seats”).
- Adding `cancel_reminder` to companion’s catalog — duplicates calendar plugin tools and pulls `ReminderStore` into `ze-personal` (rejected in 142 research).

## 2. Primary store and no dual-write (Principle VIII)

**Decision:** One primary domain write per cancel speech act. Conflict rule is already Phase 142: time/reminder beats lingering loop; multi-week outcome is a goal, not a loop. If reminder and loop both match the same words, pick one primary by that rule; do not call `forget_fact` and do not write both domain stores. Two **named** targets in one turn (“forget that I like aisle seats, and cancel the dentist reminder”) are two explicit speech acts — two tools — not a silent dual-write of one clause.

If domain cancel fails (unknown id, already fired, invalid transition), tell the truth. Do **not** fall back to `forget_fact`.

**Rationale:** FR-002 / FR-006. A “just in case” biography retract after a reminder cancel is the shim this constitution forbids.

**Alternatives considered:**
- Always try `forget_fact` after a domain miss — second fake success class; forbidden.
- Batch-cancel every fuzzy match then retract facts sharing the token — opposite of 143 precision.

## 3. Loop close has no conversational tool today

**Decision:** Add a `loops` agent in `ze-worldstate` with `@tool` wrappers around existing `review.close_loop` / `review.drop_loop` plus a list of non-terminal loops (so the agent can pick an id). Companion delegates `agent_name=loops`. Do not put loop tools on companion. Do not invent a fourth store or a new Postgres table. REST `close_loop` / `drop_loop` remain the same review functions.

**Rationale:** Reminders and goals already have owning agents and cancel/abandon tools. Loops are created by inflow and closed via REST only. Spec assumes existing `close_loop` / drop; the gap is a conversation door, not a new lifecycle. Mirroring `GoalAgent` keeps Principle III: worldstate owns the write; companion only hands off. `ze-worldstate` already depends on `ze-agents`. Wire modules through `build_worldstate_stack` / `import_agent_modules` like automation, and add paths to ze-api test `ALL_AGENT_MODULE_PATHS`.

**Alternatives considered:**
- Inject `LoopStore` into `CompanionAgent` — `ze-personal` would take a new `ze-worldstate` import and clone specialist tools (142 rejected this for reminders).
- REST-from-the-agent — wrong layer.
- Skip loops this phase — fails US1 independent test (“repeat for a loop”).

## 4. Nested tools must be visible for earned claims

**Decision:** Hard-cut `run_delegate` so `ToolCall.result` is a mapping `{ "response": <str>, "tool_calls": <list of nested ToolCall or dicts> }` instead of the specialist’s response string alone. Companion honesty reads nested `cancel_reminder` / `close_loop` / `drop_loop` / `abandon_goal` outcomes. `ToolCall.success` on `delegate_to_agent` is not enough (specialist can reply with a lie and still return).

**Rationale:** FR-004 and FR-005. Today delegate returns only `result.response`. Companion never sees `cancel_reminder`’s `{cancelled: label}`. Phase 143 already proved `success` ≠ `ok` for remember/forget. Same class here: domain confirmations must be payload-earned. Pre-v1: break the string-shaped delegate result; update in-tree callers/tests. Do not keep a string-or-dict dual reader beyond this phase.

**Alternatives considered:**
- Prompt-only “only confirm if the tool worked” on reminders/goals — 143 already showed that fails.
- Put cancel tools on companion so the gate sees them — rejected in §3 / 142.
- Gate only forgotten-fact claims (143) and ignore FR-005 — leaves “I’ve cancelled it” unearned.

## 5. Forgotten-fact claims stay 143-only

**Decision:** Do not extend `earned_forget` to domain success. `enforce_memory_confirmations` still treats forgotten-fact dialect (`I've forgotten`, `I forgot`, `forgotten that`, `wiped`, `já esqueci`) as earned solely from `forget_fact` payload `ok` true. After a successful reminder cancel, the reply may confirm the reminder was cancelled; if the model also says it forgot a memory fact, strip that sentence.

Add a sibling pass (same companion module) for **domain-cancel claims**: reminder cancelled / loop closed or dropped / goal abandoned only when the nested (or same-agent) tool succeeded this turn. Fail closed on mixed sentences. Direct `RemindersAgent` / `GoalAgent` / `loops` turns apply the same domain-claim rule on their own `tool_calls` (eval `reminders_cancel` does not go through companion). Do not implement Phase 149’s specialist remembered/forgotten dialect.

**Rationale:** Spec: domain cancel success does not license a forgotten-fact claim. FR-005 is the cancel analogue of 143, limited to cancel/close/abandon wording.

**Alternatives considered:**
- Treat any delegate success as earned forget — recreates the lie 143 closed.
- Strip all “forget” substrings including “forget the dentist” user quotes — too coarse; gate model claims, not the user’s words in a question restatement if separable.

## 6. Conservative domain match (143 spirit, not the biography ladder)

**Decision:** Do not change `cancel_reminder(reminder_id=)` / `abandon_goal(goal_id=)` / `close_loop(loop_id=)` into query-batch APIs. Add `precise_label_match(query, labels) -> unique | miss | ambiguous` in `ze_agents` (generic strings, no dentist/reminder vocabulary). Owning agents **must** list, then match, then call at most one cancel/close/abandon. If match is miss or ambiguous, do not call the write tool; ask or say so.

Match rules (first non-empty class wins; if a class has more than one hit → **ambiguous**, not batch):

1. Normalized exact equality of the stored label/title and the query (or the query after stripping cancel verbs: forget/cancel/drop/abandon/close + articles).
2. Full stored label (minimum 8 characters or 2+ tokens) appears as a contiguous phrase in the query.
3. No short-query-as-substring-of-label (query token count &lt; 2 after stripping cancel verbs, e.g. `dentist` alone against several “dentist …” labels).
4. Optional unique embedding: at most one item, cosine ≥ 0.88, runner-up &lt; 0.80 — only if an embedder is already in deps; otherwise skip. Never top-N.

Empty query / “forget that” with no referent → miss. Several reminders sharing “dentist” → ambiguous (ask which). This is **not** `_retract_facts_matching`; do not import the fact matcher into calendar.

**Rationale:** Spec edge case: do not cancel the set on a short token. LLM-only “call list then pick” will over-cancel. A hard match before the write is testable without OpenRouter.

**Alternatives considered:**
- Exact label only — deaf for “forget the dentist appointment” vs label `Call the dentist`.
- `cancel_reminder` accepts a query and deletes all ILIKE hits — batch door; forbidden.
- Reuse `_retract_facts_matching` on reminder labels — wrong store, wrong package.

## 7. Biography forget stays biography-only

**Decision:** Keep `forget_fact` and the 143 ladder unchanged. Extractor `forget` + companion `forget_fact` for R2 utterances (“Forget that I like aisle seats”). Unrelated reminders/loops/goals that merely share a word are not cancelled. Vague “forget the dentist” that matches neither a precise fact nor a unique domain item: miss both doors; do not batch-retract biography.

**Rationale:** FR-003 / US2. Closing the cancel door must not steal real forget.

## 8. Scope risks decided here (not NEEDS CLARIFICATION)

| Risk | Decision |
|---|---|
| Workflows | Out unless the user clearly names a workflow run (spec assumption). Default “forget the dentist” is reminder/loop/goal. |
| Phase 144 veto | Untouched. Companion keeps “do not block mail/calendar tools.” |
| 145 recitation | Out except 143 forgotten-fact overlap already required. |
| 147–150 | Out of scope; mention only as later honesty-roadmap items. |
| Portuguese cancel verbs | English required in tests; cheap equivalents (`cancela`, `esquece o lembrete`) optional in the same stripper, no NLP stack. |
| Delegate result shape break | In-tree tests updated this phase; no compatibility shim. |
| Embedding in label match | Optional; reminders agent may skip if no embedder in deps. Unique exact/phrase is enough for SC-001. |

## 9. Code facts (grounding)

- Companion tools: `remember_fact`, `forget_fact`, `delegate_to_agent` — `plugins/ze-personal/ze_personal/agents/companion/agent.py`. Instructions already say not to use `forget_fact` to cancel reminders; no R14 cancel-handoff lines.
- Extractor `speech_act` closed set: `fact|forget|reminder|loop|goal|ingest|drop|clarify` — `ze_memory/extractor.py`. `forget` is not distinguished from cancel-the-reminder.
- `run_delegate` returns `result=result.response` only — `ze_agents/delegate.py`.
- `cancel_reminder` → `{cancelled: label}` or `{error: ...}` — `ze_calendar/agents/reminders/tools.py`.
- `abandon_goal` → `{title, status: "abandoned"}` or `{error: ...}` — `ze_automation/agents/goals/tools.py`.
- `close_loop` / `drop_loop` — `ze_worldstate/review.py`; REST in `ze_api/api/routes/loops.py`; **no** `@tool`.
- 143 gate: `earned_forget` from `forget_fact` `ok` true only — `ze_personal/agents/companion/honesty.py`.
- Eval: `memory_speech_act_timed_reminder` covers create-not-fact; `reminders_cancel` is “Cancel my reminder about the dentist,” not companion “forget the dentist.” `memory_forget_explicit` is R2 aisle/dark-mode forget.
