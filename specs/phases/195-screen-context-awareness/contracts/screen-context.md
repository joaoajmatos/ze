# Contract: screen context, resolvers, note

Normative for FR-001 to FR-025.

## Wire (`message.context`, `WsScreenContext`)

```jsonc
{
  "place": "doing",                       // world | ask | doing | mind | governance | plugin
  "route": "/doing/workflows/w1",         // no query secrets; ≤ 200 chars
  "origin": "chat_about",                 // ask_bar (default) | chat_about | preset
  "subject":   [{ "kind": "workflow", "id": "w1", "label": "Weekly report", "component": "workflow_module" },
                { "kind": "workflow_execution", "id": "e1", "label": "Run of Oct 16", "component": "execution_row" }], // ≤ 3
  "selection": [{ "kind": "loop", "id": "L1", "label": "Reply to Ana" }],   // ≤ 20
  "visible":   [{ "kind": "goal", "id": "g1" }],                            // ≤ 30
  "focused_module": "Workflows",          // ≤ 80, a module label
  "canvas":    [{ "index": 1, "type": "claim_card", "ref": { "kind": "loop", "id": "L1" } }], // Ask only, ≤ 12
  "captured_at": "2026-10-17T14:02:11Z",
  "compose": null, "topic": null,         // phase 184
  "workspace_placed": null                 // existing
}
```

Removed (hard cut): `screen`, `goal_id`, `workflow_id`, `execution_id`.

## Kinds and resolvers

| Kind | Owner (registers) | Store call | Summary content (≤ 240 chars) | Posture |
|---|---|---|---|---|
| `goal` | ze-automation | `GoalStore.get_goal_detail` (+ `list_progress` row from 184 when present) | status; milestones done/total; next milestone; open gate title and since | kind `priority`, source `goal`, confidence none, `updated_at` |
| `goal_gate` | ze-automation | `GoalStore.get_gate` | gate title, status, fired at, parent goal title | same as goal |
| `workflow` | ze-automation | `WorkflowStore.get` + `list_executions(id, 1)` | schedule in words, enabled, last result (`failure_summary` when failed), next run | kind none, source `workflow` |
| `workflow_execution` | ze-automation | `WorkflowStore.get_execution` | status, steps run/total, duration, `failure_summary` (never raw `error`) | kind none |
| `held_write` | ze-automation | `HeldWriteStore.get` | first item's effect phrase + summary, item count, source run, expires in | kind none |
| `loop` | ze-worldstate | `LoopStore.get` | state in words, drift deadline and rationale, linked reminder/goal | `claim_kind`, `provenance` as source, `confidence`, `updated_at` |
| `entity` | ze-memory | `get_entity` + one-hop relation names (`GraphStore.expand`, cap 5) | type (person, project, …), relation names, last contact for people | kind of the entity claim if present, `updated_at` |
| `fact` | ze-memory | `get_facts_by_ids` | family, value sentence (never the raw key), review state | `claim_kind`, provenance, confidence, `updated_at` |
| `procedure` | ze-memory | procedure store lookup by id (T001 names the method) | name, version, status, last invoked | kind none |
| `skill` | ze-skills | `SkillStore.get` | name, status (pending review / approved / disabled), source | kind none |
| `workspace_run` | ze-workspace | `get_run` | command summary, status, started, exit | kind none |
| `workspace_placed` | ze-workspace | none (refs carry path and size) | the existing "files placed this turn" text | none |
| `notification` | ze-proactive | new `NotificationStore.get(id)` | title, when; then resolves its target ref (`target_type`/`target_id`, 184 table) one hop | none |
| `hypothesis` | ze-correlation | `HypothesisStore.get` | summary, relation, evidence count | `claim_kind` (inference/suspicion), confidence, `created_at` |
| `contact` | ze-personal (plugin) | `PersonStore` lookup | name, last contact, projects | per contact claim |
| `reminder` | ze-calendar (plugin) | reminder store lookup | text, fire time, linked loop | none |
| `news_article` | ze-news (plugin) | article lookup | title, source, published | none |

A resolver never returns more than one line per ref and never raises; it returns `status` per line.

## Note format

```
[Screen: Doing. What the user can see right now, read by Ze from its own records:]
Subject: Workflow · "Weekly report" — enabled, Mondays 09:00; last run failed: Step 2 of 4, "Check the inbox", failed: it ran out of time. Updated 1 d ago.
Subject: Workflow run · "Run of Oct 16" — failed after 2 of 4 steps, 41 s. (changed since you opened it)
Selected: Open loop · "Reply to Ana" — drifting since Tue; confirmed by you; confidence 0.62; source email; updated 3 d ago.
Visible: Goal · "LedgerLite launch" — active, 2/5 milestones.
+12 more on screen not included.
"this" / "it" / "that" = Workflow "Weekly report" unless the user names something else.
"these" / "those" = the 1 selected item.
The user opened this chat from that item's "Chat about this" action: lead your first reply with it.   ← origin chat_about only
Use this silently. Do not describe the screen back to the user or claim to see anything not listed here.
```

Posture wording: `suspicion` → "suspected (not confirmed)"; `inference` → "inferred"; `fact`/`identity` → no hedge word but confidence printed when < 0.9; `priority` → no claim word. Status suffixes: `(no longer exists)`, `(changed since you opened it)`, `Could not load <kind> <id>.`

Budget: `SCREEN_NOTE_CAP = 1200` characters including header and binding lines (binding and honesty lines are always kept; lines are dropped from the bottom of the priority order: canvas, visible, focused, selection, subject).

## Trace (`MessageTrace.screen`)

```jsonc
{ "place": "doing", "route": "/doing/workflows/w1", "origin": "chat_about",
  "subject": ["Workflow · Weekly report"], "selection_count": 1, "visible_count": 13, "canvas_count": 0,
  "focused_module": "Workflows", "captured_at": "…", "note_chars": 812,
  "resolvers": [{ "kind": "workflow", "id": "w1", "status": "ok", "ms": 14 }, { "kind": "goal", "id": "g7", "status": "cut", "ms": 0 }] }
```

Trace label: `Asked about: <kind> · <title>` when `origin == "chat_about"`, else `Asked from: <Place> · <first subject title>` (or `Asked from: <Place>` with no subject).
