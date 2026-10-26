# Data Model: Judgment Surface

No database change and no migration. Every type here is an in-process dataclass. The trace row types (`JudgmentTrace`, `JudgmentBar` in `ze_core/conversation/messages/types.py`) keep their shape, so REST, the `trace_update` frame and the message store do not change.

## New: `ze_agents.judgment`

### `SurfaceBar` (frozen dataclass)

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | The config key, for example `choice_trust` |
| `value` | `float` | In [0, 1] |

### `SurfaceConfig` (frozen dataclass, base class)

| Member | Kind | Notes |
|---|---|---|
| `enabled` | field, `bool = False` | Every subclass keeps it as its first field |
| `SURFACE` | `ClassVar[str]` | Config key under `system_one.surfaces` |
| `BARS` | `ClassVar[Mapping[str, str]]` | Bar field name → the question id it governs. Every bar listed here must be set for `calibrated` |
| `EXTRAS` | `ClassVar[Mapping[str, Callable[[Any], Any]]]` | Extra field name → parser of its raw config value (the parser returns the default when the value is missing or invalid) |
| `from_settings(settings)` | classmethod | The only config parser. `settings` is a config dict or an object with `.config`. A missing block gives the defaults. `enabled` is true only for the literal `True`. Each bar goes through `parse_bar`; an invalid bar becomes `None` and logs `system_one_bar_invalid` once per surface and bar per process |
| `calibrated` | property | `enabled`, every `BARS` field not `None`, and `consistent()` |
| `consistent()` | method | `True` by default |
| `bar_for(question_id)` | method | The `SurfaceBar` of the first bar in `BARS` order that governs the question, or `None` when unset or ungoverned |

### `DecisionUse` (frozen dataclass)

| Field | Type | Notes |
|---|---|---|
| `consumed` | `frozenset[str]` | Question ids the decision used |
| `unused_reason` | `str \| None` | Why the answer was not used, from the decision; `None` when used or held under a bar |

### `Judgment` (frozen dataclass): the judgment record

| Field | Type | Notes |
|---|---|---|
| `surface` | `str` | `cfg.SURFACE` |
| `result` | `SystemOneResult` | The raw result; a raised call is `SystemOneResult(outcome="skip", skip_reason="error")` |
| `question_kinds` | `dict[str, QuestionKind]` | Every question asked, in the order asked |
| `consumed` | `frozenset[str]` | From `DecisionUse` |
| `skip_reason` | `str \| None` | `result.skip_reason or "error"` when `result.outcome == "skip"`, else `DecisionUse.unused_reason` (FR-007) |
| `bars` | `dict[str, SurfaceBar \| None]` | One entry per question id in `question_kinds`, from `cfg.bar_for` |

A surface that was not asked (disabled, uncalibrated, no client, or a surface-specific precondition) has no record.

### `NotAsked`

`Literal["disabled", "uncalibrated", "unavailable"]`, returned by `gate()`.

## Surface declarations

Field names, order and defaults are unchanged; each class gains `SURFACE`, `BARS` and `EXTRAS`.

| Class (module) | `SURFACE` | `BARS` (bar → question) | `EXTRAS` | `consistent()` |
|---|---|---|---|---|
| `RoutingSurfaceConfig` (`ze_core/routing/judge.py`) | `routing` | `choice_trust` → `agent`; `multi_specialist_hold` → `multi_specialist` | `shortlist_k` (int ≥ 2, default 5); `screen_hint` (literal `True`, default `False`) | default |
| `ComplexitySurfaceConfig` (`ze_core/routing/tier.py`) | `complexity` | `simple_max` → `needs_deep_reasoning` | none | default |
| `SkillsSurfaceConfig` (`ze_skills/judge.py`) | `skills` | `choice_trust` → `skill`; `needs_skill_hold` → `needs_skill` | `shortlist_k` (int ≥ 1, default 5, invalid logs `skills_shortlist_k_invalid`); `shortlist_floor` (a bar-shaped value, default 0.35) | default |
| `LoopGateSurfaceConfig` (`ze_worldstate/loop_judge.py`) | `loop_gate` | `loop_hold` → `is_open_concern`; `resolves_hold` → `resolves_existing` | none | default |
| `CorroborationSurfaceConfig` (`ze_worldstate/corroboration_judge.py`) | `corroboration` | `corroborate_hold` → `same_concern`; `promote_hold` → `same_concern` | none | `corroborate_hold <= promote_hold` |
| `CommitmentIntakeSurfaceConfig` (`ze_worldstate/commitment_judge.py`) | `commitment_intake` | `choice_hold` → `commitment`; `family_hold` → `family`; `biography_hold` → `biography`; `loop_hold` → `is_open_concern`; `explicit_hold` → `explicit_declaration`; `resolves_hold` → `resolves_existing` | none | default |

`commitment_judge._BAR_NAMES` and `judgment_bars._INTAKE_BARS` are deleted; `CommitmentIntakeSurfaceConfig.BARS` replaces both. `fact_judge.FactBars` is unchanged (the intake builds it from its config).

Deleted parsers: `routing_surface_config`, `complexity_surface_config`, `skills_surface_config`, `loop_gate_surface_config`, `corroboration_surface_config`, `commitment_intake_surface_config`. Callers use `<Class>.from_settings(settings)`.

Each surface module also exports `read_decision(decision) -> DecisionUse` (research R4).

## Changed carriers

| Type | Before | After |
|---|---|---|
| `RoutingJudgment` (`ze_core/routing/types.py`) | `result`, `question_kinds`, `consumed`, `skip_reason` | deleted |
| `RoutingEnvelope.judgment` | `RoutingJudgment \| None` | `Judgment \| None` |
| `TierOutcome.judgment` (`ze_core/routing/tier.py`) | `RoutingJudgment \| None` | `Judgment \| None` |
| `SkillsJudgment` (`ze_skills/types.py`) | four fields | deleted |
| `SkillMatchOutcome.judgment` | `SkillsJudgment \| None` | `Judgment \| None` |
| `LoopAdmission` (`ze_worldstate/types.py`) | `decision`, `judgment: SystemOneResult \| None`, `question_ids`, `question_kinds`, `consumed`, `skip_reason`, `commit`, `source` | `decision`, `judgment: Judgment \| None`, `commit`, `source` (203 later changes `commit` and `source`) |
| `IntakeAdmission` (`ze_worldstate/intake.py`) | `outcome`, `fact`, `loop`, `links`, `judgment: SystemOneResult \| None`, `question_kinds`, `consumed`, `skip_reason`, property `question_ids` | `outcome`, `fact`, `loop`, `links`, `judgment: Judgment \| None` |
| `FactAdmission` (`ze_memory/types.py`) | `facts`, `path`, `judgment`, `question_ids`, `consumed`, `skip_reason` | `facts`, `path` |
| `TierJudge` (`ze_core/routing/tier.py`) | `warn_uncalibrated_once()`, `_uncalibrated_warned` | both deleted |

`LoopInflow.finish(text, provenance, decision, *, judgment=None, question_ids=(), skip_reason=None)` becomes `finish(text, provenance, decision, *, judgment: Judgment | None = None)`.

## Trace rows (ze-core)

`judgment_rows(judgment: Judgment) -> list[JudgmentTrace]` replaces `judgments_from_result(result, *, question_kinds, consumed, skip_reason, surface, bars)`:

- `result.outcome != "ok"`: one row per question id, `kind` from `question_kinds`, `skip_reason=judgment.skip_reason`, `surface`, `bar`, `latency_ms`.
- `result.outcome == "ok"`: one row per question id; a missing answer gives a skip row with `skip_reason=judgment.skip_reason`; an answer gives the answer value, Choice probabilities and peakedness, `model`, `input_tokens`, `consumed=qid in judgment.consumed`, `skip_reason=judgment.skip_reason`.
- `bar` is `JudgmentBar(b.name, b.value)` for a `SurfaceBar`, else `None`.

These are the rules of today's `judgments_from_result`; only the inputs change.

## Checkpoint allowlist

`CORE_CHECKPOINT_MODULES` (`ze_core/checkpoint_serde.py`) gains `ze_agents.judgment` and `ze_agents.system_one`, because `RoutingEnvelope` is checkpointed with the graph state and now carries a `Judgment` holding a `SystemOneResult`.
