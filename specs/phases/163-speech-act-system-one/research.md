# Research: Speech-Act System One (163)

All Technical Context unknowns were resolved during scope pinning (spec Clarifications, 2026-10-08) and by reading the code at `f5ac9d2f`/`5855427b`. No NEEDS CLARIFICATION remains.

## R1 — Who writes the fact value

- **Decision**: System One judges first. On **persist**, a narrowed Haiku prompt (`_VALUE_SYSTEM`) writes `{"facts": [{"value": "..."}]}` only. The predicate is the System One family. On **skip**, the unchanged pre-163 `_SYSTEM` prompt runs.
- **Rationale**: System One returns labels and probabilities, never text (ADR "What System One is"). Keeping act and family out of the writer's output means there is never a second judge (FR-006). Haiku now runs only on persist turns, which are a minority, instead of on every non-trivial turn.
- **Fact confidence**: The writer gets a fixed `0.8`, the same default `raw_to_facts` already uses. Neither the Noul nor Choice peakedness is copied into `Fact.confidence`, because ADR anti-patterns forbid conflating calibrated P(yes) with Ze's decaying claim confidence. The value writer is not asked for a confidence, since that would be a judgment.
- **Alternatives rejected**: (a) store the raw utterance as the value, which hurts dedup, contradiction NLI and recall phrasing; (b) keep the full Haiku JSON and only use System One as a veto, which is two judges on every turn and fails "replace the judge."

## R2 — Proving behavior when evals skip extraction

- **Fact (code)**: `write_memory` sets `is_eval = thread_id.startswith("eval-")` and skips episode, fact, event and entity extraction. Every eval runner path prefixes `eval-` (`ze_eval/runner.py:282`, `server.py`, `api/routes/eval.py`).
- **Decision**: Keep the skip (FR-013). Proof comes from three things:
  - unit fixtures with a fake `SystemOneClient` returning gold answers (EN+PT), plus a fake `complete` that counts calls;
  - `eval/calibration/speech_act.jsonl`, a labeled set of at least 3 EN and 3 PT per act, with gold act, gold family and gold `persist` boolean;
  - `eval/calibration/speech_act.py`, an opt-in live run (requires `OPENROUTER_API_KEY`) that asks the production questions per row, shuffles Choice option order (eval only, per ADR), and prints exact-act accuracy, a confusion matrix, fact precision/recall at candidate bars, a reliability table for Choice confidence, and suggested `choice_hold`/`biography_hold`. It runs via `make calibrate-speech-act`. It is not a pytest module.
- **Alternatives rejected**: removing the `eval-` skip, which would contaminate eval runs with extraction writes and verifier cleanup churn; a `@pytest.mark.slow` live test, which asserts pass/fail and does not report calibration numbers.

## R3 — Default posture and unset bars

- **Decision**:
  ```yaml
  system_one:
    surfaces:
      speech_act:
        enabled: false
        choice_hold: null      # uncalibrated — set from `make calibrate-speech-act`
        biography_hold: null   # uncalibrated — independent of choice_hold
  ```
  `enabled: true` with either bar `null` logs `speech_act_system_one_uncalibrated` (warning, once per turn) and goes down the skip path to Haiku. A disabled global `system_one.enabled` already yields a `disabled` skip from `DisabledSystemOneClient`.
- **Rationale**: FR-010. Cookbook numbers never ship. "Hold everything" would silently stop all fact admission.

## R4 — Getting judgments onto the trace

- **Fact (code)**: The graph runs `record_trace → write_memory → END`. `record_trace` copies `state["judgments"]` into a new `MessageTrace`. The WS turn handler reads `outcome.final_state["message_trace"]` after the graph completes, and `NativeAppInterface.send_with_thread` then calls `save_trace` and sends the **final** `trace_update` frame from that object.
- **Decision**: `write_memory` returns `{"message_trace": replace(trace, judgments=trace.judgments + new)}` when a judgment was made and `state["message_trace"]` exists. Because the final frame and the persisted row both come from `final_state`, judgments appear live on the final frame and on reload. Only the earlier partial streaming frames (phase 95) lack them. This needs no new frame and no graph reorder.
- **Conversion**: Add `judgments_from_result(result, *, question_ids: Sequence[str], consumed: frozenset[str], skip_reason: str | None = None) -> list[JudgmentTrace]` in `ze_core/conversation/messages/judgments.py`. On ok, it produces one row per answered question. `answer` is the choice label, or the noul float for a Noul. `peakedness` is `answer.confidence` for Choice and `None` for Noul (the 162 UI contract says not to invent confidence for a noul). `model` is the reported model and `input_tokens` the input usage. On skip, it produces one row per id in `question_ids` (a skip result carries no answers) with `skip_reason` set, `answer=None` and `consumed=False`.
- **Consumed**: Persist marks all three consumed. Hold marks the question(s) whose bar failed or whose label stopped persistence (for example, a `reminder` act consumes only `speech_act`). Skip marks none.
- **ze-memory boundary**: ze-memory returns the raw `SystemOneResult` plus the consumed ids inside `FactAdmission` and never imports ze-core.

## R5 — Single attempt on this surface

- **Fact (code)**: `OpenRouterSystemOneClient.evaluate` loops over `_BACKOFFS = [1.0, 2.0, 4.0]` with a per-attempt timeout, which can add seconds before the fallback starts.
- **Decision**: Hard-cut the Protocol to `evaluate(state, questions, *, max_attempts: int | None = None)`. `None` keeps the 162 behavior of `len(_BACKOFFS)` attempts. `max_attempts=1` means one POST: any retryable status maps straight to its skip reason with no sleep. `max_attempts` below 1 is `invalid_request`. `DisabledSystemOneClient` accepts the keyword and ignores it. The speech-act judge always passes `1`.
- **Alternatives rejected**: a separate client instance per surface, which duplicates DI for one integer; changing the global default, which would pre-empt 164's choice.

## R6 — Question design

- **State**: `{"user": prompt, "assistant": response[:1000]}`. This matches today's Haiku input cap and nothing more (FR-005, ADR pinned #6).
- **Questions** (one batched `evaluate`, ADR pinned #7):
  - `speech_act` (Choice): options in `SpeechAct` enum order. Each option has its own criterion taken from the 142/146 rules: time wins over biography; cancel aimed at a reminder, loop or goal is that act; biography retract is `forget`. Criteria carry EN and PT examples ("lembra-me terça às 3", "esquece o dentista", "prefiro lugar no corredor").
  - `family` (Choice): `identity`, `preference`, `relationship`, `constraint`, `contact_detail`, `drop`. Criteria per family; `drop` covers mood, weather, schedule and commitments.
  - `biography` (Noul): "Does the user's message state a durable fact about themselves that would still be true in a month?"
- **Why ask family and biography on every call**: Questions are batched in one request and output tokens are free. Asking them conditionally would need a second round-trip. Judgments only enter the decision when the act is `fact`; otherwise they are recorded as not consumed.

## R7 — Decision table (pure code)

Evaluated in order. The first match wins.

| # | Condition | Decision | Consumed |
|---|---|---|---|
| 1 | trivial turn or `[ERROR]` response | `none` (no call at all) | — |
| 2 | surface disabled, or a bar unset | `skip` → Haiku judge | — |
| 3 | `result.outcome == "skip"` | `skip` → Haiku judge | — |
| 4 | an expected answer missing or of the wrong type | `skip` (reason `invalid_answer`, logged) → Haiku judge | — |
| 5 | `admit_speech_act(choice) != FACT` | `hold` | `speech_act` |
| 6 | `speech_act.confidence < choice_hold` | `hold` | `speech_act` |
| 7 | `admit_family(family.choice) is None` | `hold` | `speech_act`, `family` |
| 8 | `family.confidence < choice_hold` | `hold` | `speech_act`, `family` |
| 9 | `biography.noul < biography_hold` | `hold` | all three |
| 10 | otherwise | `persist(family)` → value writer | all three |

- Rule 5 runs before rule 6. A confident `reminder` and an unsure `reminder` both hold, and only `fact` needs to be confident. One `choice_hold` applies to both Choices. That is legitimate because both are Choice peakedness. `biography_hold` is a separate Noul bar (FR-002).
- Rule 4 is the only place an *answer* leads to Haiku, and it covers a malformed answer, not an unsure one. That keeps FR-006 intact: unsure means hold.
- Rule 9 enforces US3 scenario 2 (biography near even plus Choice `fact` → no persist). SC-003's "even band" is any Noul below `biography_hold`. Calibration is expected to put that bar above 0.5.

## R8 — Callers of `gather_fact_proposals`

- `ze_api/container.py:280` and `ze_core/container.py:446` register it as `fact_extractor` in `configurable`. Its only consumer is `write_memory`. Tests: `ze-core/tests/orchestration/nodes/test_memory.py`, `test_extractor_dual_write.py`, `test_context_continuity_composition.py`, and ze-memory `test_extractor.py`. All move to `FactAdmission` in the same change (hard cut).

## R-follow-up — Questions labelled as facts (System One Tuning floor, 2026-10-12)
The original case (a user question labelled a `fact` speech act) is not recorded in the repo, so the calibration set had no question rows. Added 12 (6 EN, 6 PT, gold `drop`): questions that ask for, or mention, a fact about the user ("what's my sister's name again?", "prefiro lugar no corredor ou à janela?").
Before any change, 8 of the 12 came back as `fact` (4 per language), at Choice confidence 0.28–0.88; exact-act accuracy fell from 0.967 to 0.806 and ECE rose from 0.036 to 0.104. The shipped bars still held: at `choice_hold` 0.9 and `biography_hold` 0.7 fact precision stayed 1.00 (recall 0.93), because every mislabel was below 0.9. The act label was wrong but nothing persisted.
Fix: the `fact` criterion now says a question is never a fact, and the `drop` criterion names questions to the assistant. Rerun: all 12 questions answer `drop`; accuracy 35/36 per language (0.972), ECE 0.042; shipped bars unchanged (precision 1.00, recall 0.93). The one miss is the earlier `drop` row labelled `reminder` ("I'll call Mom Tuesday").
