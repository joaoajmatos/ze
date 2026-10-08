# Quickstart: Routing Choice After E5 (164)

## Prove it offline (default)

```bash
make test-core          # routing judge, router, factory, judgments, nodes
make test-agents        # Protocol unchanged
make test            # ze-api: container wiring uses the factory
make test-memory        # 163 caller of judgments_from_result still passes
```

All of these use a fake `SystemOneClient`. None calls OpenRouter.

## Measure the bars (opt-in, costs credits)

```bash
export OPENROUTER_API_KEY=sk-or-...
make calibrate-routing
```

It runs `eval/calibration/routing.jsonl` live (option order shuffled), then prints Choice accuracy vs the gold agent, the peakedness reliability table, `none` precision/recall, multi-specialist Noul separation, Score separation, and suggested `choice_trust`, `multi_specialist_hold` and `complexity_lookup_max`.

## Turn it on

In `apps/ze-api/config/config.yaml` set `system_one.enabled: true` and `surfaces.routing.enabled: true`, then paste the measured bars. A `null` bar means skip with a warning log and the 160 path.

## Check a turn

Send a close-gap single-specialist prompt. In the trace panel, "Judgments" shows `agent` (consumed), `multi_specialist` and `complexity` rows; "Routing" shows `embedding` with the Choice peakedness as `% conf` and no Haiku step.
