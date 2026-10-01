# Data Model: Speech-Act System One

**Feature**: `163-speech-act-system-one`

No new Postgres tables, no migrations. Judgments reuse `MessageTrace.judgments` (phase 162).

## AdmissionThresholds (frozen dataclass, `ze_memory.speech_act_gate`)

| Field | Type | Rules |
|---|---|---|
| `act_min_peakedness` | `float` | Choice `confidence` floor for `speech_act` |
| `family_min_peakedness` | `float` | Choice `confidence` floor for `family` |
| `biography_min` | `float` | Noul floor for "durable biography" |

Built by `thresholds_from_settings(settings)`. Returns `None` (surface off) unless `system_one.enabled`, `surfaces.speech_act.enabled`, and all three keys are numeric.

## AdmissionDecision (dataclass)

| Field | Type | Rules |
|---|---|---|
| `outcome` | `"admit"` \| `"hold"` \| `"skip"` | `skip` = System One returned `outcome="skip"`; legacy judge runs |
| `family` | `str \| None` | Set only on `admit`; always a `KEEP_FAMILIES` member |
| `judgments` | `list[dict]` | Rows shaped like `JudgmentTrace` |

## Decision table

| Condition (checked in order) | Outcome |
|---|---|
| System One result `skip` | `skip` |
| No `speech_act` answer | `hold` |
| `admit_speech_act(choice)` is not `fact` (unknown → `drop`) | `hold` |
| act peakedness missing or < `act_min_peakedness` | `hold` |
| `family` or `biography` answer missing | `hold` |
| `admit_family(choice)` is `None` | `hold` |
| family peakedness missing or < `family_min_peakedness` | `hold` |
| biography Noul missing or < `biography_min` | `hold` |
| otherwise | `admit` (family = admitted family) |

## Judgment rows

Question ids: `speech_act`, `family`, `biography`. On skip: one `speech_act` row with `skip_reason`. `consumed=True` for `speech_act` whenever answered; for `family` and `biography` only once the act was `fact` and peakedness cleared, so those two were actually evaluated.

## Config

```yaml
system_one:
  surfaces:
    speech_act:
      enabled: false
      # act_min_peakedness / family_min_peakedness / biography_min — uncalibrated
```
