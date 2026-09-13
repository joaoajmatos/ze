# REST Contract: Priority Snapshot & Override

All routes under `/api/v0/priority`, `HTTPBearer` auth
(`dependencies=[Depends(require_api_key)]`), pattern-matched against
`apps/ze-api/ze_api/api/routes/collisions.py` and `loops.py`.

## `GET /api/v0/priority/snapshot`

- `operation_id`: `getPrioritySnapshot`
- `summary`: "Get the current priority snapshot"
- `description`: "Return PriorityView's ranked loops, stuck/near-gate goals, and
  non-stale hypotheses, merged with any active user reprioritizations (FR-001,
  FR-008, FR-009, FR-010)."
- `response_model`: `PrioritySnapshotItem[]`

```
PrioritySnapshotItem:
  source_kind: "loop" | "goal" | "hypothesis"
  source_id: UUID
  title: str
  displayed_rank: int          # after override merge (data-model.md "Ranking merge")
  computed_rank: int           # PriorityView's unmodified rank, always present
  overridden_from_computed: bool   # FR-010 in-view indicator
  override:                    # null when no active override exists for this item
    pinned: bool
    anchor_source_kind: "loop" | "goal" | "hypothesis"
    anchor_source_id: UUID
    relation: "above" | "below"
    submitted_at: datetime
```

Empty list (not an error) when nothing is open across all three sources
(User Story 1, Acceptance Scenario 2).

## `POST /api/v0/priority/override`

- `operation_id`: `submitPriorityOverride`
- `summary`: "Submit a user reprioritization"
- `description`: "Drag-path entry point (FR-002). Submits a user-stated
  Contribution through the validated write path (FR-004/FR-005) targeting the
  named anchor item. Superseding an existing override for the same item is
  implicit (FR-012)."
- Request body:

```
PriorityOverrideRequest:
  source_kind: "loop" | "goal" | "hypothesis"
  source_id: UUID
  anchor_source_kind: "loop" | "goal" | "hypothesis"
  anchor_source_id: UUID
  relation: "above" | "below"
  pinned: bool = false
```

- `response_model`: `PrioritySnapshotItem` (the affected item's row, post-merge)
- Errors:
  - `404` — `source_id` or `anchor_source_id` does not currently exist in any
    of the three `PriorityView` source lists (FR-011's "stale target" case
    applied at submission time, not just at later render time).
  - `422` — validation failure surfaced from `validate_and_submit`
    (`UnlicensedClaimKindError`, `MissingEvidenceError`, `DanglingEvidenceError`
    — expected not to occur in normal operation given R1's fixed
    `source_function`/`claim_kind`, but mapped defensively).
  - On any submission failure (this route's write, or the collision-detector
    side-channel raising rather than fire-and-forgetting — should not happen
    per `submit_and_detect_collisions`'s fail-open design, but the route layer
    still catches and reports) — FR-015: the response is a non-2xx error, and
    the frontend (per `research.md` R9/contracts/tool-contract.md) reverts the
    drag and shows an inline error rather than assuming success.

## `POST /api/v0/priority/override/{override_id}/unpin`

- `operation_id`: `unpinPriorityOverride`
- `summary`: "Unpin a priority override"
- `description`: "Clears the `pinned` flag on an active override, converting it
  back to a fresh decaying override starting from now (FR-009's 'until the user
  unpins it' path)."
- `response_model`: `PrioritySnapshotItem`
- Errors: `404` if `override_id` does not reference a currently-active override.

Note: there is no separate "delete override" endpoint — a user clears an
override by submitting a new one that matches `PriorityView`'s own unmodified
position (supersession, FR-012), or by unpinning (above) and letting it decay
(R6). This keeps one write path (POST /override) as the sole mutation entry
point per FR-004, rather than a second bespoke deletion mechanism.
