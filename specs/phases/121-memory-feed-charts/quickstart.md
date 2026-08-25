# Quickstart: Validating Memory Feed Charts

## Prerequisites

- `make dev-full` running, with facts/episodes recorded across several weeks (real usage or seeded).

## 1. Validate the backend change

```bash
make test-memory
```

Confirm a test asserts `get_memory_activity` returns `fact_count`/`episode_count` per day summing to `count`.

## 2. Validate the growth chart (User Story 1)

1. Open `/brain/memory`.
2. Confirm a chart shows memory volume over time, distinct from the `TimelineScrubber`'s density strip and the feed list below.
3. Drag the timeline scrubber to an earlier date; confirm the growth chart updates to reflect that as-of state (not live data) — this also re-validates research.md R4's fix.

## 3. Validate the composition chart (User Story 2)

1. Confirm a chart shows the facts-vs-episodes proportion.
2. Filter the feed to "Facts" only via the existing filter chips; confirm this doesn't change the composition chart (composition reflects total memory, not the current list filter) — or, if the plan decides otherwise during implementation, that the chosen behavior is intentional and documented.

## 4. Validate edge cases

- New account, 1-2 days of memory — growth chart renders sensibly.
- Account with only facts, zero episodes — composition chart shows a clear single-category state.
- Narrow viewport — both charts remain legible.
