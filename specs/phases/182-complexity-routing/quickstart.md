# Quickstart: Complexity Routing (182)

## Offline (free)

```bash
make test-core                                   # tier node, decide_tier, router hard cut, trace
make test                                        # ze-api: schemas, container wiring, calibration scorer
make test-py                                     # every Python suite (CI gate)
make test-web                                    # RoutingBadge tier line
make calibrate-complexity ARGS="--check-sets"    # both files: schema, quotas, language balance; no network
python eval/calibration/routing.py --recall      # routing calibration still runs without gold_complexity
rtk proxy grep -rn "ComplexityEstimator\|complexity_lookup_max\|complexity_source" --include='*.py' --include='*.yaml' --include='*.md' core apps eval docs README.md AGENTS.md   # expect only specs/ history
```

Expected with the shipped config (surface enabled, `simple_max` 0.40): a single-agent turn for companion, research or goals carries a `needs_deep_reasoning` row in `judgments` and a `tier` record (`system_one`); calendar, reminders, messenger and the other agents without a `model_simple` show `no_simple_model` and make no request. With `enabled: false` every trace shows `tier.decided_by == "off"` and the full model, and no `needs_deep_reasoning` row.

## Dev run (shipped config, surface on)

```bash
make dev-full
```

Send "thanks!" and "help me decide between two job offers" to companion. Open the trace: "thanks!" shows "Light model · System One" and the decision is a Noul at or below 0.40; the job-offers message shows "Full model · System One". Set `system_one.surfaces.complexity.enabled: false` and reload: both show "Full model · tiering off". `routing_log` rows have no `complexity` / `model_selected` columns after `make migrate`.

## Live calibration (costs credits; ENG lead)

```bash
OPENROUTER_API_KEY=... make calibrate-complexity                                  # tuned set: report + suggested simple_max
OPENROUTER_API_KEY=... make calibrate-complexity ARGS="--set holdout --simple-max <frozen>"   # once, verdict
```

The figures and the verdict are in research.md R12 (held-out ENABLE for EN and PT, 2026-10-16). The enable commit (`enabled: true`, `simple_max: 0.40`, dated comment) is separate from the implementation commits (FR-020).
