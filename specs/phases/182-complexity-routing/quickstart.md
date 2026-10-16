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

Expected with the shipped config: every turn's trace shows `tier.decided_by == "off"` and the full model; no `needs_deep_reasoning` row in `judgments`.

## Dev run (shipped config, surface off)

```bash
make dev-full
```

Send "thanks!" and "help me decide between two job offers" to companion. Open the trace: both show "Full model · tiering off". `routing_log` rows have no `complexity` / `model_selected` columns after `make migrate`.

## Live calibration (costs credits; ENG lead)

```bash
OPENROUTER_API_KEY=... make calibrate-complexity                                  # tuned set: report + suggested simple_max
OPENROUTER_API_KEY=... make calibrate-complexity ARGS="--set holdout --simple-max <frozen>"   # once, verdict
```

Record the figures and the verdict in research.md (R12, added at run time). ENABLE for EN and PT → a separate commit sets `enabled: true` and `simple_max`, with a dated comment.
