# Quickstart: Speech-Act System One (163)

Validate post-turn admission with System One. Routing (164) is out of scope.

## Prerequisites

- 162 is merged: `SystemOneClient` is in `ze_sdk`, `system_one` is in config, and `MessageTrace.judgments` exists.
- `make install`.

## Default posture (no behavior change)

`apps/ze-api/config/config.yaml`:

```yaml
system_one:
  enabled: false
  surfaces:
    speech_act:
      enabled: false
      choice_hold: null
      biography_hold: null
```

With this config, extraction runs the pre-163 Haiku judge (SC-007).

## Unit checks (no live vendor)

```bash
make test-agents   # Protocol carries max_attempts
make test-core     # client honors max_attempts=1 (no sleep); judgments_from_result; write_memory trace merge
make test-memory   # decide() table; gather_fact_proposals persist/hold/skip/uncalibrated; gold EN+PT fixtures
make test          # ze-api wiring still boots with the new config block
make lint
```

Expected:
- The dentist-cancel fixture gives `reminder` and the aisle-retract fixture gives `forget`, in EN and PT, and neither persists (SC-002).
- Timed-reminder, loop and goal fixtures give zero facts (SC-001).
- A Noul under `biography_hold` with Choice `fact` gives zero facts and zero `complete` calls (SC-003, SC-006).
- A client skip makes exactly one `complete` call (the full judge) and leaves no duplicate identities after the 148 filter (SC-004).
- Enabled with a `null` bar logs a warning and takes the Haiku path.
- No test POSTs to `openrouter.ai` (SC-005).

## Calibration (opt-in, live, costs credits)

```bash
OPENROUTER_API_KEY=sk-or-... make calibrate-speech-act
```

This runs `eval/calibration/speech_act.py` over `eval/calibration/speech_act.jsonl` with model `typesafe/jev-1.13` and shuffled option order. It prints per-language exact-act accuracy, a confusion matrix, a Choice-confidence reliability table, fact precision/recall across a bar grid, and suggested `choice_hold` / `biography_hold` (SC-008). Copy the suggested bars into config and set `system_one.enabled: true` and `surfaces.speech_act.enabled: true`. Re-run whenever the pinned model id changes.

## Manual smoke (optional, dev)

After calibration, in a non-eval chat session:
1. "Remind me Tuesday at 3 to call the dentist." The "Why?" panel shows three judgments with `speech_act=reminder` consumed and no new `memory_facts` row.
2. "I prefer aisle seats." A `preference` fact is written and all three judgments are consumed.
3. Stop network access or blank the key. The turn still completes, the panel shows skip rows, and the fact path matches pre-163.
