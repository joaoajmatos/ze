# Data Model: Speech-Act System One (163)

No database change. All types are in-process dataclasses. The persisted shape is the existing 162 `JudgmentTrace` inside `messages.trace`.

## `SpeechActSurfaceConfig` (ze-memory, `speech_act_judge.py`)

| Field | Type | Source | Rule |
|---|---|---|---|
| `enabled` | `bool` | `system_one.surfaces.speech_act.enabled` | default `False` |
| `choice_hold` | `float \| None` | `…speech_act.choice_hold` | `None` = uncalibrated; must be in `[0, 1]` when set |
| `biography_hold` | `float \| None` | `…speech_act.biography_hold` | `None` = uncalibrated; independent of `choice_hold` |

`calibrated` is true only when `enabled` and both bars are not `None`. Built by `speech_act_surface_config(settings)`, which takes either a dict or an object with a `.config` dict, the same tolerance as `fact_extraction_model`. A missing block becomes disabled. A bar that is out of range or not numeric is treated as `None` with a warning.

## `AdmissionDecision` (ze-memory, `speech_act_judge.py`)

| Field | Type | Meaning |
|---|---|---|
| `kind` | `Literal["persist", "hold", "skip"]` | outcome of `decide()` |
| `family` | `str \| None` | keep family when `persist`, else `None` |
| `reason` | `str` | `persist`; hold reasons `not_fact`, `act_unsure`, `family_drop`, `family_unsure`, `not_biography`; skip reasons `uncalibrated`, `invalid_answer`, or the client `SkipReason` |
| `consumed` | `frozenset[str]` | question ids that decided the outcome (R7 table) |

`decide(result: SystemOneResult, cfg: SpeechActSurfaceConfig) -> AdmissionDecision` is pure, with no I/O and no logging side effects beyond the return value.

## `FactAdmission` (ze-memory, `types.py`) — new return type of `gather_fact_proposals`

| Field | Type | Meaning |
|---|---|---|
| `facts` | `list[Fact]` | facts to submit (may be empty) |
| `path` | `Literal["system_one", "haiku", "none"]` | `system_one` = decided by System One (persist or hold); `haiku` = pre-163 judge ran; `none` = no client, trivial turn or `[ERROR]` |
| `judgment` | `SystemOneResult \| None` | raw result when System One was called (ok or skip); `None` when not called |
| `question_ids` | `tuple[str, ...]` | ids sent to System One (empty when not called); lets ze-core write skip rows |
| `consumed` | `frozenset[str]` | from `AdmissionDecision`; empty on skip |
| `skip_reason` | `str \| None` | decision-level skip reason, which can be `uncalibrated` or `invalid_answer` even when the client returned `ok` |

Invariants:
- `path == "haiku"` ⇒ `consumed` is empty.
- `path == "system_one"` and `facts` non-empty ⇒ every `fact.predicate` equals the decided family.
- There is never more than one generative judge per turn.

## `JudgmentTrace` (ze-core, existing — 162)

Unchanged. Mapping from `SystemOneResult` (`judgments_from_result`):

| `JudgmentTrace` field | ok answer | skip |
|---|---|---|
| `question_id` | `speech_act` / `family` / `biography` | each id in `FactAdmission.question_ids` |
| `kind` | answer `type` | question `type` |
| `answer` | `choice` (Choice) or `noul` (Noul) | `None` |
| `probabilities` | Choice distribution; `None` for Noul | `None` |
| `peakedness` | `confidence` for Choice; `None` for Noul | `None` |
| `model` | `result.model` (reported id) | `None` |
| `input_tokens` | `result.input_tokens` | `None` |
| `latency_ms` | `result.latency_ms` | `result.latency_ms` |
| `consumed` | `question_id in FactAdmission.consumed` | `False` |
| `skip_reason` | `FactAdmission.skip_reason` when set (e.g. `invalid_answer`), else `None` | client `skip_reason` (or decision skip reason) |

Uncalibrated or disabled-surface turns never call the client, so they add no judgment rows.

## Calibration row (`eval/calibration/speech_act.jsonl`)

| Field | Type | Rule |
|---|---|---|
| `id` | string | unique |
| `lang` | `"en" \| "pt"` | |
| `user` | string | user utterance |
| `assistant` | string | short plausible reply (≤ 1000 chars) |
| `gold_act` | one of the eight `SpeechAct` values | |
| `gold_family` | keep family or `drop` | `drop` unless `gold_act == fact` |
| `gold_persist` | bool | true only for durable biography |
| `source` | string, optional | e.g. `memory_speech_act_timed_reminder`, `146-dentist`, `146-aisle` |

The set must include the gold pairs from SC-002 (dentist-cancel → `reminder`, aisle-retract → `forget`) in both languages, plus every `memory_speech_act_*` and `memory_admission_*` prompt.
