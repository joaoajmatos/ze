# Contract: Speech-act judgment

**Feature**: `163-speech-act-system-one`
**Verbatim**: `speech_act`, `SpeechAct`, `KEEP_FAMILIES`, `admit_speech_act`, `admit_family`, `SystemOneClient`

## Module

`core/cognition/ze-memory/ze_memory/speech_act_judge.py`. It imports `ze_agents.system_one` types only, never `ze_core`.

Public names:
- `SPEECH_ACT_QUESTIONS: dict[str, SystemOneQuestion]` with keys `speech_act`, `family`, `biography`
- `build_state(prompt: str, response: str) -> dict` returns `{"user": prompt, "assistant": response[:1000]}`
- `SpeechActSurfaceConfig`, `speech_act_surface_config(settings)`
- `AdmissionDecision`, `decide(result, cfg)`

## Questions

| Id | Type | Options / prompt | Notes |
|---|---|---|---|
| `speech_act` | `choice` | `fact`, `forget`, `reminder`, `loop`, `goal`, `ingest`, `drop`, `clarify`, in `SpeechAct` enum order | `criteria` is a dict, one criterion per label. Encodes 142 R11 (time wins), 146 (cancel aimed at reminder/loop/goal is that act; biography retract is `forget`), 147 (ingest). Each criterion has ≥1 EN and ≥1 PT example. |
| `family` | `choice` | `identity`, `preference`, `relationship`, `constraint`, `contact_detail`, `drop` | `drop` covers mood, weather, schedule, commitments, right-now location |
| `biography` | `noul` | "Does the user's message state a durable fact about themselves that would still be true in a month?" | separate bar (`biography_hold`) |

The option set must equal `{a.value for a in SpeechAct}` and `KEEP_FAMILIES ∪ {"drop"}`. A unit test asserts this so the closed sets can't drift. Option order is fixed in production. Only the calibration script shuffles it.

## Call

```python
result = await system_one_client.evaluate(
    build_state(prompt, response), SPEECH_ACT_QUESTIONS, max_attempts=1
)
```

At most one call per turn. No call for trivial turns, `[ERROR]` responses, `eval-` sessions (handled by `write_memory`), a disabled surface, or unset bars.

## Decision

The R7 table in [research.md](../research.md) is normative. Answer labels pass through `admit_speech_act` / `admit_family` before comparison, so an unknown label becomes `drop`/`None` and leads to hold.

## Config

```yaml
system_one:
  surfaces:
    speech_act:
      enabled: false
      choice_hold: null      # uncalibrated — from `make calibrate-speech-act`
      biography_hold: null   # uncalibrated — independent of choice_hold
```

## Logging

`get_logger(__name__)` events:
- `speech_act_system_one_decision` with `kind`, `reason`, `family` and `latency_ms`. It never logs user text.
- `speech_act_system_one_uncalibrated` (warning).
- `speech_act_system_one_invalid_answer` (warning).
