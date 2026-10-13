# Contract: `track_loop`

## Tool declaration

```python
@tool(
    access=ToolAccess.WRITE,
    description=(
        "Start tracking an open loop the user explicitly asked you to keep in mind "
        "(e.g. 'keep that on my radar'). `title` is a short phrase in the user's "
        "language naming the matter, under ten words. Pass `window_days` only if the "
        "user named a timeframe, as whole days; otherwise leave it 0. Call once per "
        "distinct concern. Only tell the user it is tracked if this returned ok true."
    ),
    reversibility=ToolReversibility.REVERSIBLE,
    undo_tool="drop_loop",
    undo_note="Dropping removes the loop from your radar, including an existing loop that was only reinforced.",
    effect_phrase="started tracking an open loop",
)
async def track_loop(loop_tracker: LoopTracker, title: str, window_days: int = 0) -> dict
```

`loop_tracker` is an injected dep (not in the LLM schema: its annotation is not primitive). `window_days` is coerced with the `_whole_days` rules, then clamped 1..365; invalid or <1 means 7.

## Results

Success: `{"ok": true, "outcome": "created|confirmed|reinforced|revived", "id": "<uuid>", "title": "...", "state": "active"}`

Failure (never raises): `{"ok": false, "error": "<short reason>"}` for empty title, store error, seam rejection (`ContributionRejectedError` or equivalent `ZeError`), lost revive race (`InvalidLoopTransitionError`).

## Agent instructions (replace the `_AGENT_INSTRUCTIONS` block)

Add `- track_loop: start tracking a concern the user explicitly asked you to keep in mind`. Rules: call `track_loop` when the user asks to keep/hold/watch something (EN or PT); one call per distinct concern; do not call it for a worry the user only describes; on `outcome` created/confirmed say it is now tracked, on reinforced say it was already tracked, on revived say it was back on the radar; on `ok: false` say you could not track it and why in one short sentence; never claim tracking without a successful call this turn. The existing close/drop rules stay verbatim.

## Gate skip predicate

```python
def track_loop_succeeded(tool_calls: list[ToolCall]) -> bool   # ze_agents/nested_tools.py
```
True when any `flatten_tool_calls(...)` entry has `tool_name == "track_loop"` and `tool_payload(result).get("ok") is True`. In `write_memory`, `loop_admission = None` for the turn when true (log `write_memory_loop_gate_skipped_track`).

## Claim patterns (`_TRACK_CLAIM`, applied only with `strip_track_claims=True`)

Case-insensitive. A sentence containing `?` is never a claim.

| Strip (no earned call) | Keep |
|---|---|
| "I'll keep that on my radar." | "Want me to keep this on your radar?" |
| "I'm keeping an eye on it." | "You have 3 open loops: ..." |
| "It's on your radar now." | "I could not track that." |
| "I've started tracking the Porto move." | "Tracking requires a clear title." (no claim shape) |
| "I'll keep track of it." | |
| "Fico atento a isso." | "Queres que fique atento?" |
| "Já está no meu radar." | |
| "Vou acompanhar isso." | |
| "Fica no teu radar." | |
| "Estou a acompanhar o assunto." | |

Earned flag `track_loop_earned(calls)` = `track_loop_succeeded(calls)`. When the whole reply is stripped the text is `COULD_NOT_TRACK = "I could not track that."`. The mixed-claim rule (a forget claim next to a real claim) is extended to treat a track claim like cancel/close/abandon.
