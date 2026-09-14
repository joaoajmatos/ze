# Contract: `PriorityView`'s relationship-staleness source

This is the seam that lets `core/ze-priority` (a `core/` package with no
domain knowledge, per Constitution III) rank a `plugins/ze-personal`
(domain) signal without either package importing the other's concrete
types — the same shape as Phase 60's `SignalSource` protocol. See
research.md §3 for the full rationale.

## Protocol (new, defined in `core/ze-priority`)

```python
# core/ze-priority/ze_priority/types.py (or a new protocols.py)

class RelationshipStalenessSource(Protocol):
    async def list_stale_for_follow_up(
        self, stale_days: int, limit: int
    ) -> list[StaleFollowUpNudge]: ...
```

`StaleFollowUpNudge`-equivalent fields required: `name: str`, `days_ago: int`
(mirrors `plugins/ze-personal/ze_personal/contacts/types.py`'s existing
`StaleFollowUpNudge` exactly — `ze-priority` defines its own structurally
identical type, e.g. `RelationshipSignal`, so it never imports
`ze_personal.contacts.types`).

## Conformance (no plugin-side code change required)

`plugins/ze-personal/ze_personal/contacts/store.py`'s `PersonStore` already
exposes `list_stale_for_follow_up(self, stale_days: int, limit: int) ->
list[StaleFollowUpNudge]` (`store.py:388-409`). Because Python `Protocol`s
are structural, `PersonStore` satisfies `RelationshipStalenessSource`
without declaring it, importing it, or being modified.

## Wiring (composition root only)

```python
# apps/ze-api/ze_api/container.py
priority_view = PriorityView(
    loop_store=...,
    goal_store=...,
    hypothesis_store=...,
    relationship_source=person_store,  # new — PersonStore instance
)
```

No other package constructs `PriorityView` with the fourth argument in
production code; every existing unit test that builds `PriorityView` with
three stores continues to pass it (see data-model.md §6 — the parameter is
optional).

## Behavioral contract

- `PriorityView.rank()` calls `relationship_source.list_stale_for_follow_up(
  stale_days, limit)` inside its own try/except block, same as the other
  three sources (FR-009/FR-010).
- If `relationship_source` is `None`, the relationship source is skipped
  silently — not counted toward `failed`, not counted toward "all sources
  failed."
- If `relationship_source` raises, it's added to `failed` and ranking
  continues over the remaining sources — matching existing FR-009 behavior,
  generalized from "3 of 3 failed" to "all *supplied* sources failed."
- `stale_days`/`limit` passed to `list_stale_for_follow_up` are
  `PriorityView`'s own values (not the retired `briefing.py` config keys —
  research.md §6) — this phase does not specify their exact source in this
  contract; that's an implementation-task-level decision (e.g. a
  `ze-priority`-owned default, analogous to how goal/loop staleness
  thresholds are already owned by their respective core packages, not by
  the briefing job).
