# Quickstart: System One Client (162)

Validate the **client and trace hook**, not speech-act or routing. Those are 163/164.

## Prerequisites

- Repo install: `make install` / `make web-install` as usual.
- `OPENROUTER_API_KEY` may be empty. 162 must still boot.
- Do **not** set a TypeSafe-native key. Do **not** expect chat completions to answer Jev questions.

## Config

`apps/ze-api/config/config.yaml` should contain `system_one.enabled: false` (or omit the block and code-default to disabled). Pin `model: typesafe/jev-1.13` when the block is present.

## Unit checks (no live vendor)

From repo root:

```bash
make test-agents      # Protocol / dataclasses if tests live there
make test-core        # HTTP client mocked; record_trace copies judgments
make test             # ze-api schema for judgments
make test-web         # trace panel empty-safe + populated section
make lint
```

Expected:

- Default tests never POST to `openrouter.ai`.
- Fake client: a noul of `0.9` is readable as a float, not scraped from a paragraph.
- Fake choice: label + probability map + peakedness present.
- Missing key + enabled: `evaluate` returns skip `missing_key`, does not raise.
- Timeout / 429: skip, does not raise.
- Disabled: skip `disabled`; no HTTP.
- `from ze_sdk import SystemOneClient` does not import `ze_core`.
- `MessageTrace` with two `judgments`, one `consumed=True`, round-trips through `asdict` / schema.

## Optional live probe (not CI)

Only if a maintainer opts in with a real `OPENROUTER_API_KEY` and `system_one.enabled: true`: POST one noul over a tiny `state` string to `/api/v1/systemone` with model `typesafe/jev-1.13`. Confirm `answers.<id>.type == "noul"` and that the reported `model` is stored. Mark any such test `@pytest.mark.slow`.

## Production turn (162)

With default config, a normal chat turn must match pre-162 routing envelopes, extracted facts, and skill matches on existing fixtures (SC-002). Trace `judgments` is `[]`.

## Follow-on

163 and 164 consume `configurable["system_one_client"]`. Do not start them in this tree.
