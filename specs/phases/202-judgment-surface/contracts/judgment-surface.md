# Contract: `ze_agents.judgment`

The Python interface every judgment point uses. Types are in [data-model.md](../data-model.md). This file is the contract step (`lead`, T002–T007): the other lanes build against it.

## Public names

```python
# core/contracts/ze-agents/ze_agents/judgment.py
SurfaceBar          # frozen dataclass: name, value
SurfaceConfig       # frozen dataclass base: enabled; ClassVars SURFACE, BARS, EXTRAS;
                    # from_settings(), calibrated, consistent(), bar_for()
DecisionUse         # frozen dataclass: consumed, unused_reason
Judgment            # frozen dataclass: surface, result, question_kinds, consumed, skip_reason, bars
NotAsked            # Literal["disabled", "uncalibrated", "unavailable"]

def surface_block(settings: Any, surface: str) -> dict | None: ...          # moved from system_one.py
def parse_bar(value: Any, name: str, *, surface: str) -> float | None: ...  # moved; logs system_one_bar_invalid once
def gate(cfg: SurfaceConfig, client: SystemOneClient | None) -> NotAsked | None: ...
async def judge(
    client: SystemOneClient,
    cfg: SurfaceConfig,
    state: str | dict,
    questions: Mapping[str, SystemOneQuestion],
    decide: Callable[[SystemOneResult], D],
    read: Callable[[D], DecisionUse],
) -> tuple[Judgment, D]: ...
def reset_surface_warnings() -> None: ...   # tests only
```

`surface_block` and `parse_bar` leave `system_one.py` (hard cut; no re-export). After this phase `surface_block` has one caller, `SurfaceConfig.from_settings` (SC-003).

## Behaviour

### `gate(cfg, client)`

1. `not cfg.enabled` → `"disabled"`.
2. `not cfg.calibrated` → log `system_one_surface_uncalibrated` (`surface=cfg.SURFACE`) at warning, at most once per surface per process, then `"uncalibrated"`.
3. `client is None` → `"unavailable"`.
4. Otherwise `None`. Never raises.

### `judge(...)`

1. `await client.evaluate(state, dict(questions), max_attempts=1)`.
2. Any exception → log `system_one_judgment_error` (`surface`, `error`) at warning, and use `SystemOneResult(outcome="skip", skip_reason="error")`.
3. `decision = decide(result)`; `use = read(decision)`.
4. Return `Judgment(surface=cfg.SURFACE, result=result, question_kinds={qid: q.type ...}, consumed=use.consumed, skip_reason=..., bars={qid: cfg.bar_for(qid) ...})` and `decision`.
   `skip_reason` is `"error"` when step 2 caught an exception; else `result.skip_reason` when `result.outcome == "skip"` (a skip with no reason stays `None`, as `judgments_from_result` does today); else `use.unused_reason`.

`judge()` never raises unless `decide` or `read` raises; every existing `decide()` is total.

### `SurfaceConfig.from_settings(settings)`

- `surface_block(settings, cls.SURFACE)`; `None` → `cls()`.
- `enabled = block.get("enabled") is True`.
- each name in `BARS`: `parse_bar(block.get(name), name, surface=cls.SURFACE)`.
- each name in `EXTRAS`: `parser(block.get(name))`.
- `cls(enabled=..., **bars, **extras)`.

## Call sites (one per surface)

| Surface | File and function | Before `gate` | Between `gate` and `judge` | After `judge` |
|---|---|---|---|---|
| routing | `ze_core/routing/router.py` `EmbeddingRouter._judge` | `state is None` or fewer than 2 ranked → no record | shortlist; fewer than 2 names → no record | record onto `RoutingEnvelope.judgment` |
| complexity | `ze_core/orchestration/nodes/tier.py` `choose_tier`, `ze_core/routing/tier.py` `TierJudge.choose` | `compound`, `off` (no judge), `no_simple_model` | `gate` result maps `disabled` → `off`, `uncalibrated` → `uncalibrated` | `TierOutcome.judgment`; node writes `judgment_rows` |
| skills | `ze_skills/matching.py` `SkillMatcher.match` | no `judgment_state`, no client or nothing scored → E5 matches | shortlist; empty → E5 matches | `SkillMatchOutcome.judgment` |
| loop_gate | `ze_worldstate/admission.py` `LoopInflow._judge` | empty text → `hold/trivial` | unsupported provenance → `fallback/unavailable` | `finish(..., judgment=record)` |
| corroboration | `ze_worldstate/corroboration.py` `_corroborate`, `_judge` | — | independence rule | `_judge` returns `(record, decision)` |
| commitment_intake | `ze_worldstate/intake.py` `CommitmentIntake.admit` | empty or trivial prompt → `hold/trivial` | — | fallback kinds → `_fallback(..., judgment=record)`; others → `_apply` |

`gate` returning a reason maps to today's outcome at each site: routing and skills fall back to E5 with no record; the loop gate returns `fallback/<reason>`; corroboration links only; the intake runs `_fallback` with that reason and no record.

## Trace rows

`ze_core/conversation/messages/judgments.py`:

```python
def judgment_rows(judgment: Judgment) -> list[JudgmentTrace]: ...
```

Rules in [data-model.md](../data-model.md#trace-rows-ze-core). Callers: `embed_route`, `match_skills`, `choose_tier`, `write_memory` (commitment intake only). No caller passes a bar map, a kind map or a surface name.

## Skip reason by surface

| Case | routing | skills | complexity | commitment_intake | loop_gate (log) | corroboration (log) |
|---|---|---|---|---|---|---|
| call raised | `error` | `error` | `error` | `error` (new: rows written) | `error` | `error` |
| client skip | client reason | client reason | client reason | client reason | client reason | client reason |
| ok, invalid answer | `invalid_answer` | `invalid_answer` | `invalid_answer` | `invalid_answer` | `invalid_answer` | `invalid_answer` |
| ok, held under a bar | none (`abstain`, `drop`) | none | none | none (`hold`) | none (`hold`) | none (`not_same`) |
| ok, used | none | none | none | none | none | none |
