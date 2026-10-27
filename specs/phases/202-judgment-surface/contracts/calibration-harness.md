# Contract: calibration harness and golden checks

Owner: lane `calib`. Research R13–R15.

## Files

| File | Status |
|---|---|
| `eval/calibration/harness.py` | new |
| `eval/calibration/{routing,skills,complexity,loop_gate,corroboration,commitment_intake}.py` | refactored onto the harness |
| `eval/calibration/commitment_intake_baseline.py` | refactored where it repeats harness pieces |
| `eval/calibration/open_query.py` | row helpers only (`load_jsonl`, `norm`, `blind_overlap`, `shape_report`) |
| `eval/calibration/companion_research_check.py` | unchanged (no shared piece) |
| `apps/ze-api/tests/calibration/replay.py` | new: `ReplayClient`, `HashEmbedder`, `FakeHaiku` |
| `apps/ze-api/tests/calibration/capture_golden.py` | new: writes `golden/*.txt` |
| `apps/ze-api/tests/calibration/golden/` | new: captured outputs, committed |
| `apps/ze-api/tests/calibration/test_calibration_golden.py` | new |

Runners import the harness as a sibling: `sys.path.insert(0, str(Path(__file__).resolve().parent))`, then `import harness` (the pattern `commitment_intake.py:43` already uses).

## Harness interface

```python
# rows
def load_jsonl(path: Path, make_row: Callable[[dict], R]) -> list[R]   # raises on duplicate id
def norm(text: str) -> str                                            # casefold, collapse whitespace
def blind_overlap(a: Iterable[str], b: Iterable[str]) -> set[str]     # normalised texts in both
def language_counts(rows: Iterable[R], lang_of=...) -> Counter[str]
def shape_report(problems: list[str]) -> int                          # prints, returns exit code 0/1

# config, production parser only
def load_config(path: Path = CONFIG) -> dict
def surface_config(cls: type[C], *, enabled: bool = True, **bars: float | None) -> C
    # builds {"system_one": {"surfaces": {cls.SURFACE: {...}}}} and calls cls.from_settings
def configured(cls: type[C]) -> C                                     # cls.from_settings(load_config())
def parse_bar_list(text: str, names: Sequence[str]) -> dict[str, float]   # "--bars 0.6,0.8"
def model_from_config() -> str | None

# live run
def make_client(args) -> SystemOneClient | None                      # None + message when no key
async def run_live(client, rows, state_of, questions_of, concurrency) -> dict[str, SystemOneResult]

# reports
def reliability_bins(points: Iterable[tuple[float, bool]], edges=...) -> list[Bin]
def print_reliability(title: str, bins: list[Bin]) -> None
def bar_grid(axes: Mapping[str, Sequence[float]], metric: Callable[[dict[str, float]], M]) -> list[tuple[dict[str, float], M]]
def print_grid(title: str, grid, columns: Sequence[str]) -> None
def print_verdict(by_language: Mapping[str, tuple[bool, list[str]]], detail: Mapping[str, str]) -> bool

# results
def save_results(path: Path, results: Mapping[str, SystemOneResult | Mapping[str, SystemOneResult]]) -> None
def load_results(path: Path) -> dict[str, ...]                        # round-trips save_results exactly

# cli
def common_args(p: argparse.ArgumentParser, *, sets: Sequence[str], seed: int | None = None) -> None
    # --check-sets --set --bars --model --timeout-ms --concurrency --seed --save --load
def held_out_warning() -> None
```

The lane may rename or merge these while it builds, if the golden test stays green and SC-004's structural list holds. It must not move per-surface scoring, quotas, gold columns, baselines or acceptance rules into the harness (FR-011).

## Rules

- Every surface config a runner builds goes through `surface_config` or `configured`. No runner constructs a `*SurfaceConfig` directly (checked by a grep test).
- Every runner calls the production `decide()` and the production question and state builders. Shuffled question orders (routing, commitment intake) keep their seeds.
- `--load PATH` skips the client and reports from saved results; `--save PATH` writes them after a live run. Both work on every System One runner.
- A held-out run keeps each runner's refusal and acceptance rules unchanged (US3 scenario 2), including complexity's `VERDICT_MARKER`/`--rerun` and commitment intake's `SPENT_SETS`.
- Every flag a runner has today keeps its name and meaning (the Makefile, `docs/eval.md`, `docs/system-one.md` and `docs/configuration.md` use them). `common_args` adds only flags a runner lacks and registers each shared flag once.

## Golden checks

`capture_golden.py` runs before any runner changes (T025), against the code on the contract-step commit:

| Runner | Modes captured (today's flags) |
|---|---|
| routing | `--check-sets`; `--recall`; live run on the default datasets |
| skills | `--recall`; live run |
| complexity | `--check-sets`; tuned run; `--set holdout --simple-max 0.40 --rerun` with `VERDICT_MARKER` patched to a temp path |
| loop_gate | `--check-sets`; tuned run; `--set holdout --bars 0.75,0.8` |
| corroboration | `--check-sets`; tuned run; `--set holdout --bars 0.6,0.8` |
| commitment_intake | `--check-sets`; tuned run with `--save`; `--replay` of that file; `--set holdout3 --replay <file>` with a results file the capture builds from `ReplayClient` (spent sets refuse a live run) |
| open_query | `--check-sets` |

Patched for every live mode: `OPENROUTER_API_KEY=replay`, `ze_core.openrouter.system_one.OpenRouterSystemOneClient` → `ReplayClient`, each runner's E5 loader → `HashEmbedder`, the loop-gate Haiku client → `FakeHaiku`. `ReplayClient` derives each answer from `sha256(json(state, sort_keys) + question_id)`: a Noul in [0, 1], a Choice over the criteria keys with probabilities and a confidence, `latency_ms` from the hash, fixed `model`. Lines that depend on wall-clock time (for example complexity's `live run took …s`) are replaced with a fixed token in both the capture and the test. No capture writes outside a temp directory. The refactored runners' `--load` replaces commitment intake's `--replay` only if the golden output stays identical; otherwise `--replay` stays as that runner's name for it.

`test_calibration_golden.py`:

1. each captured mode reproduces its golden file exactly;
2. each live mode, run again with `--save tmp`, then with `--load tmp`, prints the same report (T036, once `--save`/`--load` exist);
3. `loop_gate.py`'s "no bar pair passes" path runs without error (R15; no golden, the old code raises).

The `--set holdout*` modes run against the replay client, so they spend nothing and record nothing; they check the code path, not the set.

## SC-004 check

`T037` measures `wc -l eval/calibration/*.py` (harness included) against the baseline 4,838 (the total must be at most 4,257, a 12% drop) and greps that `load_rows`, `_norm`, `report_reliability`, `report_grid`, `save_results`, `load_results`, `parse_bars`, `config_model`, `system_one_config` and `config_system_one` are not defined in any runner.
