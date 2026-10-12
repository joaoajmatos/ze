# Quickstart: Routing Choice Criteria (167)

Offline (free):
```bash
make test-core && make test-agents && make test-personal
for d in routing routing_holdout routing_holdout2; do
  uv run python eval/calibration/routing.py --dataset eval/calibration/$d.jsonl --recall --k 10
done
```
Expect the recall sweep table up to the roster size and the smallest k with recall ≥ 0.95 on all sets.

Live (costs credits; the user runs these):
```bash
make calibrate-routing            # routing.jsonl (tuning)
uv run python eval/calibration/routing.py --dataset eval/calibration/routing_holdout.jsonl --dataset eval/calibration/routing_holdout2.jsonl --k <chosen>
uv run python eval/calibration/companion_research_check.py --live
```
Expect the verdict block: per-set per-language accuracy, ECE, research→companion misses, and PASS/FAIL per acceptance rule.
