# Quickstart: Loop Extraction Gate

```bash
make test-worldstate        # gate, admission, 109 fixtures unchanged
make test-core              # write_memory node: rows, trivial skip, eval/retry guard
make test                   # ze-api: config, calibration dataset shape
make lint

python eval/calibration/loop_gate.py --check-sets   # offline, no credits: dataset shape + held-out disjoint
make calibrate-loop-gate                            # LIVE, costs credits: System One + Haiku baseline, held-out verdict
```

Enable only on an `ENABLE` verdict for both languages: set `system_one.surfaces.loop_gate.enabled: true` and the three bars in `apps/ze-api/config/config.yaml`, then record the baseline and the numbers in the tuning note of the spec.

The held-out set `eval/calibration/loop_gate_holdout.jsonl` is never edited to make a run pass. After any tuning change that followed a held-out run, write a fresh held-out file before the next verdict.
