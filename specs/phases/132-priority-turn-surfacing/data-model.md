# Data Model: Priority Turn Surfacing

No new tables and no new Alembic chain. This phase is a read-side consumer of
`PriorityView` plus the existing `priority_overrides` merge (Phase 127).

## `PriorityItem` (additive fields — `ze_priority.types`)

Existing ranking row. Three optional fields are filled at score time so
`TurnSurfacing` can relevance-filter without re-querying goal/hypothesis stores:

| Field | Type | Notes |
|---|---|---|
| `linked_entity_ids` | `tuple[UUID, ...]` | Empty for loops (overlap is graph-side). Copied from `Hypothesis.entities` at `score_hypothesis`. |
| `match_text` | `str` | Empty for loops. Goals: `title + " " + objective`. Relationships: `name`. |
| `hedge` | `bool` | `True` for unconfirmed hypotheses (Phase 130 posture). `False` otherwise. |

No new identity; `source_kind` / `source_id` / `title` / `rank` / `priority`
stay as Phase 123/128 defined them. `merge()` still keys on `source_id` only.

## `OpenItemMention` (new — in-memory, `ze_priority.types`)

The mention `TurnSurfacing` returns to `surface_loops` / resume recap. Replaces
`DriftingLoopMention` on the conversation path. `DriftingLoopMention` remains
for any leftover `LoopSurfacer` tests; the graph node no longer consumes it.

| Field | Type | Notes |
|---|---|---|
| `source_kind` | `SourceKind` | `loop` / `goal` / `hypothesis` / `relationship` |
| `source_id` | `UUID` | Same as `PriorityItem.source_id` |
| `title` | `str` | Display title |
| `mention_text` | `str` | Hedged one-liner (`format_hedged_mention` for loops and unconfirmed hypotheses; plain "still open" phrasing for goals and relationship nudges) |

## `ResumeRecap` (reshape — `ze_core.orchestration.nodes.context`)

| Field | Change |
|---|---|
| `open_loop_lines` | **Removed** |
| `in_flight_goal_lines` | **Removed** |
| `open_item_lines` | **Added** — merged `PriorityView` titles/mention lines, already in rank order |
| `session_narrative` | Unchanged |
| `in_flight_workflow_lines` | Unchanged (not a `PriorityView` source) |

`has_content()` / `render()` treat `open_item_lines` as the single "Still open:"
block.

## `AgentContext.open_priorities_note` (additive — `ze_agents.types`)

Runtime-only, never checkpointed (same as `resume_recap`). Set by
`fetch_context` when `TurnSurfacing.is_global_open_query(prompt)` is true.
Rendered into the system prompt; never appended to `messages`.

## Component payload (hard cut)

Unsolicited mentions still ride `AgentState.components`. Shape after this phase:

```jsonc
{
  "type": "open_items",
  "title": "Still open",
  "items": [
    {
      "id": "<uuid>",
      "source_kind": "goal",
      "title": "Ship the contract",
      "mention_text": "…"
    }
  ]
}
```

Replaces `type: "drifting_loops"` / `loops: [...]`. No dual-read.

## Validation / degrade rules

- Relevance is a gate: a globally top-ranked item with no overlap is dropped
  (FR-003). An explicit what's-open query skips that gate (assumption in spec).
- Unsolicited list length ≤ 3 (research.md R5). Global recap / what's-open use
  the full merged snapshot.
- `ZePriorityError` or missing `turn_surfacer` → empty mention, turn continues.
- Override-store failure → unmerged `rank()` order, turn continues.
- One failed `PriorityView` source → remaining items still usable (existing
  `rank()` contract).
