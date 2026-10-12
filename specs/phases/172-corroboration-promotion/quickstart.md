# Quickstart: Corroboration Promotion (172)

## Default build (surface off)

```bash
make test-worldstate test test-messenger test-calendar test-ingestion
make test-pg                                              # needs Docker; applies zw003 and runs the pg tests
make lint
```

Expected: 170's extraction tests pass unchanged; origin source rows are written; no System One request is made.

## Calibration

```bash
python eval/calibration/corroboration.py --check-sets   # offline shape check
make calibrate-corroboration                             # LIVE, tuned set only: grid, E5 baseline, suggested bars
python eval/calibration/corroboration.py --set holdout --bars 0.70,0.85   # the single verdict run
```

Expected: a per-language `ENABLE` or `KEEP OFF` with the failing clause (contract: [corroboration-judgment.md](contracts/corroboration-judgment.md); rule: spec FR-020). Only on `ENABLE` for EN and PT do you set `system_one.surfaces.corroboration` in `apps/ze-api/config/config.yaml`, with a comment that records the run.

## Manual check (surface on, dev stack)

1. `make dev-full`. In chat (thread A): "I still haven't sorted out the deposit with the landlord." `GET /api/v0/loops` shows a `suspected` loop with `source_inflows: ["conversation"]`.
2. In a new chat thread (thread B): "The agency emailed again, I still need to sign the deposit form." The loop becomes `active`, `promoted: true`, `source_inflows: ["conversation"]` (two conversation keys); the detail lists two sources with the score.
3. Repeat step 2 in thread B: nothing changes (`corroboration_skipped reason=same_source` in the log).
4. Drop the loop on `/loops`. Say the original sentence again in thread C: a new suspected loop may appear; a further message in thread B does not promote it (`dropped_source`).
