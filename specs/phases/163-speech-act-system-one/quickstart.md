# Quickstart: Speech-Act System One (163)

Validate the **admission gate**, not routing. Routing Choice is 164.

## Prerequisites

- Repo install: `make install`.
- 162 is Implemented (`SystemOneClient` on `configurable["system_one_client"]`).
- `OPENROUTER_API_KEY` may be empty. With the surface off (the shipped default) nothing changes.

## Config

Shipped default in `apps/ze-api/config/config.yaml`:

```yaml
system_one:
  enabled: false
  surfaces:
    speech_act:
      enabled: false
```

To enable, set `system_one.enabled: true`, `speech_act.enabled: true`, and **all three** bars. Missing any bar keeps the surface off and the pre-163 judge runs:

```yaml
      act_min_peakedness: <measured>
      family_min_peakedness: <measured>
      biography_min: <measured>
```

Do not copy cookbook numbers. Measure on Ze fixtures first, including Portuguese (T015).

## Unit checks (no live vendor)

From repo root:

```bash
make test-memory   # gate, thresholds, hold/skip/fallback — mocked clients
make test-core     # judgments attach to the recorded trace; 148 dual-write still holds
make lint
```

Expected:

- "remind me Tuesday to call Mom at 3" → no fact, no LLM call.
- "forget that I like aisle seats" → `forget`; "forget the dentist" → `reminder`; neither persists a fact.
- "I prefer aisle seats" with high peakedness and biography Noul → one fact, worded by one LLM call.
- Unknown label (`banana`) → drop.
- Choice peakedness below the bar, or biography Noul near `0.5` → no fact and no Haiku tie-break.
- System One skip (timeout, 429/529, disabled) → pre-163 extractor runs exactly once.
- Trivial turn ("thanks!") → System One is never called.
- Surface off → System One is never called.

## Trace check

On a turn that reaches the gate, the trace "Judgments" section (from 162) shows `speech_act`, and `family` + `biography` when the act was `fact`. Deciding questions are `consumed`. A skip shows one `speech_act` row with its `skip_reason`.

## Optional live probe (not CI)

Only if a maintainer opts in with a real `OPENROUTER_API_KEY`: enable the surface with measured bars on a dev instance, send the fixtures above, and compare the trace judgments to gold. Mark any automated version `@pytest.mark.slow`.

## Production turn (163)

With default config, a normal chat turn must extract the same facts as pre-163 on existing fixtures (SC-001): the legacy judge runs and `judgments` stays `[]`.

## Follow-on

164 consumes the same client for routing. Do not start it in this tree.
