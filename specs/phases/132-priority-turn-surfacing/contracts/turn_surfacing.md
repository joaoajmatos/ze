# Contract: Conversation-turn `PriorityView` consumer

Internal Python interface. No new REST routes (Phase 127 already shipped
`GET /api/v0/priority/snapshot`). Identifiers pinned by the spec: `PriorityView`,
`surface_loops`.

## `ze_priority.turn.TurnSurfacing`

Constructed once in `ze_api/container.py`. Injected as
`config["configurable"]["turn_surfacer"]`. `ze-core` never imports this class.

```python
class TurnSurfacing:
    def __init__(
        self,
        priority_view: PriorityView,
        override_store: PriorityOverrideStore | None,
        graph_store: GraphStore,
        push_log: Any | None = None,
    ) -> None: ...

    async def inline_mentions(
        self,
        entity_ids: list[UUID],
        *,
        entities: Sequence[Any] = (),
    ) -> list[OpenItemMention]:
        """Merged PriorityView order, relevance-gated, at most 3 items.
        Empty list if ranking is unavailable. Never raises to the caller."""

    async def recap_mentions(self) -> list[OpenItemMention]:
        """Merged PriorityView order, no relevance gate. Empty list on total
        ranking failure. Never raises to the caller."""

    @staticmethod
    def is_global_open_query(prompt: str) -> bool:
        """True for explicit what's-open / what's-outstanding phrasing."""
```

**Preconditions**: Safe with empty `entity_ids` / `entities` (returns `[]` for
`inline_mentions`). `override_store` may be `None` (use unmerged `rank()`).

**Postconditions**:
- `inline_mentions` items are a subsequence of the merged snapshot, in displayed
  rank order, each passing R3 relevance against this turn.
- A globally high-ranked item with no topical overlap is absent.
- Loop mentions, when returned, have already written
  `worldstate_loop_inline:{source_id}` on `push_log` when a log is configured.
- Unconfirmed hypotheses have hedged `mention_text`.

**Errors**: Methods catch `ZePriorityError` and per-store exceptions internally,
log, and return `[]`. They do not fall back to `LoopSurfacer.inline_candidates`.

## `config["configurable"]["turn_surfacer"]`

Mirrors the Phase 110 `loop_surfacer` injection. `loop_surfacer` remains on the
config for `AttentionArbitrationJob` / push eligibility; `surface_loops` no
longer calls it.

Duck-typed methods the graph nodes call:

```python
class TurnSurfacer(Protocol):
    async def inline_mentions(
        self, entity_ids: list[UUID], *, entities: Sequence[Any] = ()
    ) -> list[Any]: ...
    async def recap_mentions(self) -> list[Any]: ...
    def is_global_open_query(self, prompt: str) -> bool: ...
```

Each returned object exposes `source_kind`, `source_id`, `title`, `mention_text`.

If the key is absent, `surface_loops` and the recap / what's-open branches
return no mention — same "unwired harness" behavior as today's missing
`loop_surfacer`.

## `surface_loops` node

Still registered as `"surface_loops"` in `ze_core/orchestration/graph.py`.

Behavior after this phase:

1. If `turn_surfacer` is missing → `{}`.
2. If `TurnSurfacing.is_global_open_query(state["prompt"])` → `{}` (the ranked
   list was already injected as `AgentContext.open_priorities_note` in
   `fetch_context`).
3. Else extract entity ids *and* entity records from `memory_context`; if no
   ids → `{}`.
4. `mentions = await turn_surfacer.inline_mentions(entity_ids, entities=entities)`.
5. On exception → log `inline_turn_surfacing_error`, return `{}`.
6. On non-empty mentions: set `open_item_mentions`, append an `open_items`
   component, and (non-compound turns) append mention text to `final_response`.

## `AgentContext.open_priorities_note`

Set in `fetch_context` when `turn_surfacer.is_global_open_query(prompt)`.
`BaseAgent._build_system_prompt` prepends it immediately after `resume_recap`
when present. Runtime-only; never checkpointed.

## Out of contract

- Shared daily push budget / `AttentionArbitrationJob` (FR-007).
- `LoopSurfacer.passes_push_bar` / `eligible_candidates` / `send`.
- REST snapshot routes (unchanged).
- Contribution-seam arbitration (FR-008).
