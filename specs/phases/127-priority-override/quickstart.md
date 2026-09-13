# Quickstart: User-Directed Priority Override

Validates the feature end-to-end against the three independent tests in
`spec.md`'s User Stories.

## Prerequisites

```bash
make db-up
make migrate            # applies the new zpri001 migration (priority_overrides)
make dev-full           # backend :8000 + web :5173
```

Seed data (via existing agent conversation, or directly against the stores used
in `ze-priority`'s own tests): one open loop (`state=ACTIVE`), one stuck goal,
one non-stale hypothesis — matching User Story 1's Independent Test setup.

## Scenario 1 — Snapshot view (User Story 1)

1. Open the web app, navigate to the priority snapshot view (new route/page —
   see `research.md` R10 for the entity/widget placement).
2. Assert all three seeded items appear, each labeled with its source
   (`loop`/`goal`/`hypothesis`) and title, in `PriorityView.rank()`'s order.
3. Clear all three sources (close the loop, complete the goal, let the
   hypothesis go stale) and reopen the view — assert an empty state, not an
   error (Acceptance Scenario 2).

`curl` equivalent:
```bash
curl -H "Authorization: Bearer $ZE_API_KEY" http://localhost:8000/api/v0/priority/snapshot
```

## Scenario 2 — Drag reorder (User Story 2)

1. In the snapshot view, drag the third-ranked item above the first-ranked
   item.
2. Assert (network tab, or `GET /api/v0/priority/override`'s underlying store)
   a `PriorityOverride` row was created with `anchor_source_id` = the
   first-ranked item's id, `relation="above"`.
3. Reopen the view (full page reload) — assert the dragged item is still shown
   at the requested position (Acceptance Scenario 2), and its `computed_rank`
   in the response body is unchanged from before the drag (the underlying
   `PriorityItem.priority` score is untouched).
4. Query `specs/phases/127-priority-override/contracts/rest-api.md`'s
   `priority_overrides` row directly in Postgres — confirm `submitted_at`,
   then wait past the 48h decay window (or, for a fast local check, manually
   backdate `submitted_at` in the test DB) and reopen the view — assert the
   item's `displayed_rank` has reverted toward `computed_rank` (Acceptance
   Scenario 3).
5. Re-drag the same item and toggle "pin" in the UI — assert `pinned=true` on
   the row, and that backdating `submitted_at` no longer changes
   `displayed_rank` (Acceptance Scenario 4).

## Scenario 3 — Conversational reprioritization (User Story 3)

1. With the same three items seeded, send a chat message: "the stuck report
   goal can wait" (naming the item currently ranked first, per the
   Independent Test).
2. Assert a `confirmation` WS frame arrives describing the identified item and
   requested change (FR-006/FR-007) before any write occurs.
3. Approve the confirmation (`confirm` WS frame, `choice: "approve"`).
4. Assert the next `GET /api/v0/priority/snapshot` reflects the same
   `PriorityOverride` effect Scenario 2 produced for an equivalent drag.
5. Repeat with an ambiguous phrasing (two items with similar titles) — assert
   Ze asks for clarification instead of submitting a Contribution
   (Acceptance Scenario 2), and no `PriorityOverride` row is created.

## Collision-log verification (R1)

After Scenario 2 step 1, query `ze-collision`'s `contribution_collisions` table
(Phase 126) for a recent row whose `contribution_a_source_function` /
`contribution_b_source_function` are both `executive` but whose provenances
differ (`prompt_supplied` vs `synthesized`) — present when the user's requested
position and `PriorityView`'s own computed order genuinely disagreed (FR-010's
"in addition to it being observable to Phase 126's collision detector").
