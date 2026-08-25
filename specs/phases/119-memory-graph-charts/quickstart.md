# Quickstart: Validating Memory Graph Charts

## Prerequisites

- `make db-up`, `make migrate`, `make dev-full` running.
- A user with entities that have multiple facts/episodes spread over time (real usage history, or seed data).

## 1. Validate the backend change

```bash
make test-memory   # or the ze-memory package's test target
```

Confirm a new/updated test asserts `get_entity_detail`'s fact rows include `created_at`, and that `GET /api/v0/memory/graph/entity/{id}` returns it (contracts/entity-detail-created-at.md).

## 2. Validate the entity activity chart (User Story 1)

1. In the web client, open `/brain/graph`.
2. Click an entity with facts/episodes spread across multiple weeks.
3. Confirm the detail panel shows a chart of that entity's activity over time, distinct from the flat facts/episodes lists.
4. Click a different entity with only one or two data points; confirm the chart still renders (or is gracefully omitted) rather than looking broken.

## 3. Validate the composition breakdown (User Story 2)

1. On the same graph page, confirm a chart shows the proportion of entity types (and/or relation types) currently loaded.
2. Expand a node's neighbours; confirm the composition chart updates to include the newly-loaded entities.

## 4. Validate visual consistency (User Story 3)

- Compare the graph page's toolbar/search/detail-panel styling against the Usage page (post spec-120 rework); confirm consistent tokens, spacing, typography.

## 5. Validate edge cases

- Select an entity with all activity on a single date — chart must render sensibly, not break.
- Search to an empty result / view a graph with zero loaded entities — composition chart must show a clear empty state.
- Resize the detail panel narrow — charts must remain legible.
