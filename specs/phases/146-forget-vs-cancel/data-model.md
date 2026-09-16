# Data model: Forget vs cancel

No new Postgres tables. This phase reshapes speech-act meaning, delegate payloads, and in-memory match/gate objects.

## SpeechAct (existing enum, narrowed `forget`)

`fact` | `forget` | `reminder` | `loop` | `goal` | `ingest` | `drop` | `clarify`

| Act | Cancel-phase meaning |
|---|---|
| `forget` | Biography retract only (R2). Extractor emits this when the user names a standing fact to stop remembering. |
| `reminder` | Timed ping **or** cancel/forget speech whose primary store is a reminder (R3/R4/R14). |
| `loop` | Lingering concern **or** forget/drop/close that concern (R5/R14). |
| `goal` | Multi-week outcome **or** forget/abandon that goal (R6/R14). |

`facts` MUST be empty unless `speech_act` is `fact`. Cancel speech MUST NOT emit `forget` when the primary store is reminder/loop/goal.

No new enum value for “cancel.”

## Domain cancel outcome (existing payloads, now normative for FR-005)

| Tool | Success shape | Failure shape |
|---|---|---|
| `cancel_reminder` | mapping with `cancelled` (label string); no `error` | mapping with `error` |
| `abandon_goal` | mapping with `status` equal to `abandoned` | mapping with `error` |
| `close_loop` | mapping for the closed loop (id + `state` `closed`) without `error` | error mapping / typed loop error |
| `drop_loop` | mapping for the dropped loop (`state` `dropped`) without `error` | error mapping / typed loop error |
| `forget_fact` | `{ok: true, ids: [...]}` | `{ok: false, error: ...}` |

`ToolCall.success` is not a substitute for these payloads.

## Delegate result (hard-cut)

`delegate_to_agent` `ToolCall.result`:

| Field | Type | Meaning |
|---|---|---|
| `response` | str | Specialist user-visible text |
| `tool_calls` | list | Nested `ToolCall` objects (or equivalent dicts) from `AgentResult.tool_calls` |

String-only `result` is deleted.

## Label match (new, in-memory)

Input: `query: str`, `items: list` of `{id, label}` (reminder label, loop title, or goal title).

Outcome (closed):

| Kind | Effect |
|---|---|
| `unique` | Exactly one id; agent may call the write tool once |
| `miss` | No write |
| `ambiguous` | No write; ask which |

Strip leading cancel verbs and articles from the query before matching (`forget`, `cancel`, `drop`, `abandon`, `close`, `the`, `my`, `a`, `an`). Remaining token count &lt; 2 cannot substring-match multiple labels.

## Confirmation gate (companion + owning agents)

| Field | Meaning |
|---|---|
| `earned_forget` | `forget_fact` payload `ok` true (unchanged, Phase 143) |
| `earned_reminder_cancel` | Nested or local `cancel_reminder` success payload |
| `earned_loop_close` | Nested or local `close_loop` or `drop_loop` success payload |
| `earned_goal_abandon` | Nested or local `abandon_goal` success payload |

Forgotten-**fact** claims require `earned_forget`. Cancelled-reminder / closed-loop / abandoned-goal claims require the matching earned flag. Domain success does not set `earned_forget`.

## Transitions

```text
user utterance
  → extractor speech_act (forget vs reminder|loop|goal)
  → companion: forget_fact XOR delegate(reminders|loops|goals)
  → specialist: list → precise_label_match → at most one write
  → companion gate: 143 forget claims + domain-cancel claims
  → user-visible text
```

```text
match query
  → exact label → unique or ambiguous
  → else named full label in query → unique or ambiguous
  → else optional unique embedding
  → else miss
```
