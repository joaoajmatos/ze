# Quickstart: Priority Turn Surfacing

Verify the conversation path consumes `PriorityView` without touching push.

## Tests (no live DB / LLM)

From repo root:

```bash
make test-priority
make test-core
make lint
```

`make test-priority` covers `TurnSurfacing` ranking, relevance gating, pin
order, degrade-on-total-failure, and hedged unconfirmed hypotheses.

`make test-core` covers `surface_loops` (now `turn_surfacer.inline_mentions`)
and `fetch_context` resume recap / what's-open note injection.

## Manual check (dev stack)

1. `make dev-full`.
2. Seed a drifting loop and a stuck goal that share an entity; pin the goal
   above the loop on `/priority`.
3. In chat, talk about that entity. The "Still open" mention should name the
   goal first (or only).
4. Talk about an unrelated topic. The globally top item must not appear.
5. Wait past session inactivity (or set `last_active_at` far in the past in a
   test) and send another message: resume recap "Still open" follows snapshot
   order.
6. Ask "what's open right now": one ordered list, same order as the snapshot
   page — not loops then goals.
