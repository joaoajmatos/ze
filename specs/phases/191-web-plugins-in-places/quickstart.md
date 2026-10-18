# Quickstart: Plugins in Places (W7)

## Automated
- `make test-plugin` (contribution validation), `make test` (manifest route), `make test-news`.
- `make test-web`, `make typecheck-web`, `make web-build`, `make lint`.

## Manual against `make dev-full`
1. Ask shows "What's new in my sources?" after the core Try chips; tapping it runs a normal turn (the news agent answers).
2. `/news` lands on `/ask`.
3. With a dev fixture plugin page in Mind (see tasks T005 test fixture, or a local plugin), Mind shows "From plugins"; the row opens `/mind/plugin/<path>` as modules; `/<path>` redirects there.
4. Governance › Connections still renders and saves News settings.
5. Disable News in config, restart: the chip is gone.
