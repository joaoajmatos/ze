# Contract: Confirm and Resume Offer (171)

## `review.confirm_loop(loop_store, loop_id) -> OpenLoop` (changed)

1. `loop = await loop_store.transition(loop_id, "active")` — raises `LoopNotFoundError` / `InvalidLoopTransitionError` as today (only `suspected` is allowed; `user_asked` is never passed).
2. `deadline = now(UTC) + timedelta(days=DEFAULT_DRIFT_WINDOW_DAYS)`.
3. `await loop_store.stamp_declared(loop_id, confidence=DECLARED_CONFIDENCE, deadline=deadline)`.
4. Return `loop` with `confidence=0.9`, `drift_deadline=deadline`, `drift_rationale=None`, `confirmed_at` set.

No call to `set_drift_deadline` remains in this function. REST `POST /api/v0/loops/{id}/confirm` is unchanged in shape: `{id, state: "active", confidence: 0.9}`; 404 / 409 as today.

## Tool `confirm_loop` (new, `ze_worldstate/agents/tools.py`)

```python
@tool(
    access=ToolAccess.WRITE,
    description="Confirm a suspected open loop by id after listing, when the user says to keep track of it.",
    reversibility=ToolReversibility.REVERSIBLE,
    undo_tool="drop_loop",
    undo_note="Dropping the loop removes it; it does not return it to suspected.",
    effect_phrase="confirmed an open loop",
)
async def confirm_loop(loop_store: LoopStore, loop_id: str) -> dict
```

| Case | Result |
|---|---|
| success | `{"ok": True, "id": str, "title": str, "state": "active"}` |
| bad UUID | `{"ok": False, "error": "Invalid loop ID: '<x>'"}` |
| not found | `{"ok": False, "error": "No loop found with ID <id>."}` |
| not suspected | `{"ok": False, "error": "<InvalidLoopTransitionError text>"}` |
| any other exception | `{"ok": False, "error": "could not confirm the loop"}` + warning log |

## `tracking_earned(tool_calls) -> bool` (renamed from 169's `track_loop_succeeded`, `ze_agents/nested_tools.py`)

True iff some flattened call has `tool_name in {"track_loop", "confirm_loop"}` and `tool_payload(result)` is a dict with `ok is True`. Used by `enforce_domain_cancel_confirmations` (tracking-claim guard) and `write_memory` (168 gate skip). `track_loop_succeeded` is deleted.

## Loops agent instructions (additions)

- Tools list gains: `confirm_loop: confirm a suspected loop by id when the user wants it kept`.
- "When the user answers a 'keep track of these?' question or names suspected loops to keep: call list_open_loops, match each title to a unique `suspected` loop, call confirm_loop once per loop to keep and drop_loop once per loop to discard. If the match is already active or drifting, say it is already tracked and call nothing. Say a loop is tracked only after confirm_loop or track_loop returned ok: true this turn."
- `tools = ["list_open_loops", "track_loop", "confirm_loop", "close_loop", "drop_loop"]`; intent text "List, track, confirm, close, or drop an open loop."; `description` gains `"keep the bank one"`-style confirm examples; `routing_criteria` gains "keeping or dropping loops Ze asked about (\"keep the first two\", \"fica com a do banco\")".

## `TurnSurfacing.resume_loop_offers(limit: int = OFFER_LIMIT) -> list[LoopOffer]` (new)

```
loops = await loop_store.list(states=["suspected"])           # error -> warn, return []
candidates = sorted(loops with id, key=(-confidence, -created_at.timestamp()))   # created_at None sorts last
offers = []
for loop in candidates:
    if len(offers) == limit: break
    if push_log is None: return []                              # no record possible -> no offers
    if await push_log.was_sent_within_hours(f"worldstate_loop_offer:{loop.id}", OFFER_COOLDOWN_HOURS):  # error -> warn, return []
        continue
    offers.append(LoopOffer(loop.id, loop.title, loop.provenance))
for offer in offers:
    await push_log.log(f"worldstate_loop_offer:{offer.loop_id}")   # error -> warn, keep the offer
return offers
```

## Recap block (rendered by `ResumeRecap.render`, exact text)

```
Not yet tracked (Ze noticed these; the user has not confirmed them):
- <title 1>
- <title 2>
End your reply with one short question, in the user's language, asking whether they want you to keep track of these. Do not say they are being tracked.
```

## Caps

`recap_mentions(limit: int | None = None)`: `None` returns all (tests only); resume recap passes `RECAP_LIMIT` (5); open-priorities note passes `OPEN_QUERY_LIMIT` (10). The slice is taken over the merged order.
