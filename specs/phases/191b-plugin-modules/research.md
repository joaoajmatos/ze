# Research: Plugin Modules in Slots (191b)

## R1. Module data path
- **Decision**: a module carries a Python `provider` (the plugin's read operation); ze-api's `GET /api/v0/ui/modules/{id}` calls it with the slot's subject under a 3 s timeout, validates the tree against 191a's schema and returns it with `ui_version`.
- **Rationale**: clarification Q5 (a plugin read operation per module) with one schema, one timeout and one validation point; plugins stay on `ze_sdk`.
- **Alternatives**: a REST operation per module (each plugin repeats the response model; the manifest must carry operation ids and an OpenAPI filter).
- **Bonus**: the route knows which plugin contributed the module, so it can bind every tool action in the tree to that plugin's agents and check every claim posture, which 191a alone cannot (Gauge B-1, B-7).

## R2. Slots
- **Decision**: `mind.entity`, `doing.run`, `governance.connections`, plus presets in Ask; no World slot.
- **Rationale**: clarification Q4; World ranks what plugins feed through claims and loops.

## R3. Refresh
- **Decision**: refetch on place load, on a `refresh` frame with `screen: "module:<id>"` (sent by `ze_sdk.ui.request_module_refresh` through a new `AppInterface.send_refresh`), and every 60 s only while the module is visible.
- **Rationale**: clarification Q5.

## R4. News sources facet
- **Decision**: articles with a tag exactly equal to a `topic` entity's name (`tags && ARRAY[...]`, GIN-indexed); a `claim_list` with code-set `fact` posture and `live_search` provenance.
- **Rationale**: news signals already turn article tags into `topic` entities (`ze_news/signals.py`), so the match uses the same key Mind holds.

## R5. Presets
- **Decision**: at most two plugin chips after the core chips, continuing numbering and keys; a plain prompt (clarification Q6: no plugin composed answers yet).
