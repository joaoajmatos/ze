# Tool Contract: Conversational Reprioritization

Per `research.md` R8 — a core tool (not a plugin tool), living in
`ze_priority/tools.py`, registered with `Mode.CONFIRM` capability.

## `reprioritize_item`

**Purpose**: The conversational path's entry point (FR-003). Called by the
routing layer's agentic loop when the user's message expresses a
reprioritization intent.

**Inputs**:
```
item_description: str    # the user's own phrasing naming the target item, e.g. "the Berlin move"
requested_relation: Literal["more_urgent", "less_urgent"]   # coarse direction; see Disambiguation below
pin: bool = false         # true only when the user's phrasing unambiguously requests permanence (Clarifications Session 2026-08-25, Q3)
```

**Disambiguation (FR-006)**: The tool does not accept a raw `source_id` from the
model — it re-ranks the current `PriorityView` snapshot, matches
`item_description` against item titles by embedding similarity (reusing the
same local embedder singleton `ze_core/embeddings.py`'s pattern — no new
embedding call site config), and:

- If exactly one item clears a confidence floor → proceeds, but the tool's
  response to the model includes a restatement of which item it identified,
  for the agent to confirm with the user before the write happens (Acceptance
  Scenario 1) — this restatement happens in the `DRAFT` pass of the gate (see
  Confirmation below), not as a second silent tool call.
- If zero items clear the floor, or more than one item scores within a narrow
  margin of each other → the tool returns a clarification request (no
  Contribution submitted) and the agent asks the user to disambiguate
  (Acceptance Scenario 2) rather than guessing.
- The anchor item (`anchor_source_kind`/`anchor_source_id` in the underlying
  `PriorityOverrideRequest`, data-model.md) is derived from
  `requested_relation`: `"more_urgent"` anchors above the item currently ranked
  just above the target's current displayed position; `"less_urgent"` anchors
  below the item just below it — i.e. the tool translates the user's coarse
  direction into the same anchor-relative representation the drag path
  produces (R3), rather than exposing anchor mechanics to the LLM.

**Confirmation (FR-007)**: `reprioritize_item`'s capability mode is
`Mode.CONFIRM`. `capability_check` (`ze_core/orchestration/nodes/execution.py`)
routes any subtask calling this tool through `draft_response →
await_confirmation` exactly as for other consequential agent actions — the
draft shown to the user states which item was identified and the requested
change, satisfying both FR-006's "confirm which item" and FR-007's "same
confirmation gate" in a single pause. The Contribution is submitted only on
`await_confirmation`'s resume with `GateDecision.EXECUTE` (i.e., only after the
user approves via the `confirm` WS frame) — never during the `DRAFT` pass.

**On confirmed execution**: Submits the same `PriorityOverrideRequest`-shaped
call the REST route (`contracts/rest-api.md`) uses internally — both entry
points converge on one `ze_priority` service function
(`submit_reprioritization(...)`), so FR-004's "same validated write path" holds
literally, not just conceptually, between the two intake surfaces.

**On failure (FR-015)**: If the underlying submission fails after confirmation,
the tool's result tells the agent the instruction could not be applied (with
the reason, if known), and the agent relays this to the user in its response —
no silent success is ever reported back through the graph state.
