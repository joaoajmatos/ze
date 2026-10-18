# Quickstart: Plugins in Places (W7)

## Automated
- `make test-plugin` (contribution validation), `make test` (manifest route), `make test-news`.
- `make test-web`, `make typecheck-web`, `make web-build`, `make lint`.

Routing row: `eval/calibration/routing.jsonl` gains `single-news-sources-en` ("What's new in my sources?" → `news`). A live `make calibrate-routing` run is optional and costs credits; it is not a gate.

## Manual against `make dev-full`
1. Ask shows "What's new in my sources?" after the core Try chips, numbered after them (3 or 4); tapping it runs a normal turn, and the trace panel's Routing section names the news agent. The chip comes from the manifest built at startup: after enabling or disabling News, restart the backend and reload.
2. `/news` lands on `/ask`.
3. With a dev fixture plugin page in Mind (see tasks T005 test fixture, or a local plugin), Mind shows "From plugins"; the row opens `/mind/plugin/<path>` as modules; `/<path>` shows not-found. On `/ask/plugin/<path>` (fixture page in Ask, if added) the Ask bar opens the overlay.
4. Governance › Connections still renders and saves News settings.
5. Disable News in config, restart: the chip is gone.
