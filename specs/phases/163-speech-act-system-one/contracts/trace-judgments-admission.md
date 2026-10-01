# Contract: Admission judgments on the trace

**Feature**: `163-speech-act-system-one`

Reuses `JudgmentTrace` / `MessageTrace.judgments` from phase 162 (`contracts/trace-judgments.md`). No schema change, no API change, no web change.

## Producer

`gather_fact_proposals` appends dict rows (fields of `JudgmentTrace`) to `configurable["admission_judgments"]`. `write_memory` passes a fresh list per turn and, after the extractor returns, extends `state["message_trace"].judgments` with `JudgmentTrace(**row)`. Skipped when the sink is empty or `message_trace` is `None`.

## Rows

| `question_id` | `kind` | `answer` | `peakedness` |
|---|---|---|---|
| `speech_act` | choice | chosen label | Choice `confidence` |
| `family` | choice | chosen label | Choice `confidence` |
| `biography` | noul | yes-probability | none |

On System One skip: a single `speech_act` row with `skip_reason` and `consumed=False`.

## consumed

`speech_act`: true whenever answered. `family` and `biography`: true only when the act was `fact` and its peakedness cleared, i.e. they were evaluated. Judgments produced here appear in the same trace panel section 162 added.
