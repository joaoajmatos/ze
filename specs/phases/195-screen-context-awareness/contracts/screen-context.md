# Contract: screen context, resolvers, note

Normative for FR-001 to FR-026.

## Wire (`message.context`, `WsScreenContext`)

```jsonc
{
  "place": "doing",                       // world | ask | doing | mind | governance | plugin; optional on the wire
  "route": "/doing/workflows/w1",         // no query secrets; ≤ 200 chars
  "origin": "chat_about",                 // ask_bar (default) | chat_about | preset
  "subject":   [{ "kind": "workflow", "id": "w1", "label": "Weekly report", "component": "workflow_module", "as_of": "2026-10-16T09:00:03Z" },
                { "kind": "workflow_execution", "id": "e1", "parent_id": "w1", "label": "Run of Oct 16", "component": "execution_row", "as_of": "2026-10-16T09:01:12Z" }], // ≤ 3
  "selection": [{ "kind": "loop", "id": "L1", "label": "Reply to Ana" }],   // ≤ 20
  "visible":   [{ "kind": "goal", "id": "g1" }],                            // ≤ 30
  "focused_module": "Workflows",          // ≤ 80, a module label
  "canvas":    [{ "index": 1, "type": "claim_card", "ref": { "kind": "loop", "id": "L1" } }], // Ask only, ≤ 12
  "captured_at": "2026-10-17T14:02:11Z",   // clamped server-side to receipt time; trace only, not used for staleness
  "compose": null, "topic": null,         // phase 184
  "workspace_placed": null                 // existing
}
```

Removed (hard cut): `screen`, `goal_id`, `workflow_id`, `execution_id`.

`ScreenRef`: `kind` (≤ 64, required), `id` (≤ 64, required), `label` (≤ 120), `component` (≤ 40), `parent_id` (≤ 64; required for `workflow_execution`, optional for `goal_gate`), `as_of` (the record's `updated_at` as the client displayed it, from its query data). Every field is optional on the wire except `kind`/`id` inside a ref. `from_wire` never raises: invalid values are dropped and returned as warnings (trace `invalid`).

## Kinds and resolvers

| Kind | Owner (registers) | Store call | Summary content (≤ 240 chars) | Posture |
|---|---|---|---|---|
| `goal` | ze-automation | `GoalStore.get_goal_detail` (+ `list_progress` row from 184 when present) | status; milestones done/total; next milestone; open gate title and since | kind `priority`, source `goal`, confidence none, `updated_at` |
| `goal_gate` | ze-automation | `GoalStore.get_gate(id)` (parent goal via the gate row) | gate title, status, fired at, parent goal title | same as goal |
| `workflow` | ze-automation | `WorkflowStore.get` + `list_executions(id, 1)` | schedule in words, enabled, last result (`failure_summary` when failed), next run | kind none, source `workflow` |
| `workflow_execution` | ze-automation | `WorkflowStore.get_execution(parent_id, id)`; no `parent_id` → `failed` "missing parent" (never a false "no longer exists") | status, steps run/total, duration, `failure_summary` (never raw `error`) | kind none |
| `held_write` | ze-automation | `HeldWriteStore.get` | first item's effect phrase + summary, item count, source run, expires in | kind none |
| `loop` | ze-worldstate | `LoopStore.get` | state in words, drift deadline and rationale, "has a reminder" (`reminder_id` set) / "linked to a goal" (`goal_id` set) flags from the row only | `claim_kind`, `provenance` as source, `confidence`, `updated_at` |
| `entity` | ze-memory | `get_entity` + one-hop relation names (`GraphStore.expand`, cap 5) | type (person, project, …), relation names, last contact for people | kind of the entity claim if present, `updated_at` |
| `fact` | ze-memory | `get_facts_by_ids` | family, value sentence (never the raw key), review state | `claim_kind`, provenance, confidence, `updated_at` |
| `procedure` | ze-memory | procedure store lookup by id (T001 names the method) | name, version, status, last invoked | kind none |
| `skill` | ze-skills | `SkillStore.get` | name, status (pending review / approved / disabled), source | kind none |
| `workspace_run` | ze-workspace | `get_run` | command summary, status, started, exit | kind none |
| `workspace_placed` | ze-workspace | none (refs carry path and size) | the existing "files placed this turn" text | none |
| `notification` | ze-proactive | new `NotificationStore.get(id)` | title, when; then resolves its target ref one hop: `kind` from `target_type` (`workflow_execution`, `goal_gate`, …), `id` = `target_id`, `parent_id` = `target_parent_id` (184) | none |
| `hypothesis` | ze-correlation | `HypothesisStore.get` | summary, relation, evidence count | `claim_kind` (inference/suspicion), confidence, `created_at` |
| `contact` | ze-personal (plugin) | `PersonStore` lookup | name, last contact, projects | per contact claim |
| `reminder` | ze-calendar (plugin) | reminder store lookup | text, fire time, linked loop | none |
| `news_article` | ze-news (plugin) | article lookup | title, source, published | none |

A resolver never returns more than one line per ref and never raises; it returns `status` per line. Summaries are sanitised (FR-009) before formatting.

## Note format

```
[Screen: Doing. What the user can see right now, read by Ze from its own records:]
Subject: Workflow · "Weekly report" — enabled, Mondays 09:00; last run failed: Step 2 of 4, "Check the inbox", failed: it ran out of time. Updated 1 d ago.
Subject: Workflow run · "Run of Oct 16" — failed after 2 of 4 steps, 41 s. (changed since it was shown to you)
Selected: Open loop · "Reply to Ana" — drifting since Tue; confirmed by you; confidence 0.62; source email; updated 3 d ago.
Visible: Goal · "LedgerLite launch" — active, 2/5 milestones.
+12 more on screen not included.
"this" / "it" / "that" (or the equivalent in the user's language) = Workflow "Weekly report" unless the user names something else.
"these" / "those" = the 1 selected item shown above.
The user started this chat from that item's "Chat about this" action: name it in your first sentence, then answer; do not recite the rest of the screen.   ← origin chat_about, first message only
Use this silently. Do not describe the screen back to the user or claim to see anything not listed here.
```

Binding variants: subject present → "this" = subject; no subject and exactly one included selected item → "this" = that item; selection included → "these" = "the N selected items shown above" (+ "M more not shown" when cut); nothing singled out → `Nothing on screen is singled out; if the user says "this" (or the equivalent in their language), ask which item they mean.`

Posture wording reuses 184's claim-descriptor vocabulary: `suspicion` → "suspected (not confirmed)"; `inference` → "inferred"; `fact`/`identity` → no hedge word, confidence printed when < 0.9; `priority` or no kind → no claim word. Status suffixes: `(no longer exists)`, `(changed since it was shown to you)`, `Could not load <kind>.`

Budget: `SCREEN_NOTE_CAP = 1200` characters. Fixed lines are reserved first; refs are admitted in priority order (subject 240-char estimate; selection, focused, visible, canvas 120) while they fit; refs not admitted are never loaded and are counted in "+N more on screen not included".

Sanitising (FR-009): collapse control characters and newlines to one space; strip leading `[` and quote characters; neutralise binding patterns (`"this" =`, `[Screen:`) by escaping the leading quote/bracket; cap every field.

## Trace (`MessageTrace.screen`)

```jsonc
{ "place": "doing", "route": "/doing/workflows/w1", "origin": "chat_about",
  "subject": ["Workflow · Weekly report"], "selection_count": 1, "visible_count": 13, "canvas_count": 0,
  "focused_module": "Workflows", "captured_at": "…", "note_chars": 812, "invalid": [],
  "resolvers": [{ "kind": "workflow", "id": "w1", "status": "ok", "ms": 14 }, { "kind": "goal", "id": "g7", "status": "cut", "ms": 0 }] }
// status ∈ ok | missing | changed | failed | timeout | cut
```

Trace label: `Asked about: <kind> · <title>` when `origin == "chat_about"`, else `Asked from: <Place> · <first subject title>` (or `Asked from: <Place>` with no subject).
