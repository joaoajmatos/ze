# Contract: `LoopStore` (ze-worldstate)

## Added

```python
async def resolve(
    self, loop_id: UUID, evidence: Sequence[EvidenceRef]
) -> OpenLoop | None: ...
```

- Moves the loop to `closed` iff its state is `suspected`, `active` or `drifting`, and links each `evidence` ref with `derived_from`. One transaction.
- Returns the closed loop, or `None` when nothing moved (already `closed` or `dropped`, or a concurrent resolve won). Raises `LoopNotFoundError` when the id does not exist.
- Never writes `dismissed_evidence_fingerprint`.
- Logs `open_loop_transitioned` with `from_state`, `to_state="closed"`, `event="resolve"`.

## Changed

- `OpenLoop.claim_kind` is a read-only property (`ClaimKind | None`). The `OpenLoop(...)` constructor no longer accepts `claim_kind`.
- `create(loop)` no longer writes `claim_kind`. `get`, `list`, `list_by_evidence`, `list_drift_candidates`, `promote` and `transition` return loops whose kind is derived.

## Unchanged

- `transition(loop_id, new_state, *, user_asked=False)` and `_ALLOWED_TRANSITIONS`: `suspected → closed` is still refused there.

## New public helper

```python
def loop_claim_kind(state: LoopState) -> ClaimKind | None: ...
```

Exported from `ze_worldstate.types`.
