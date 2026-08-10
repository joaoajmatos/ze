# Quickstart: Validating Session Context Continuity

## Prerequisites

- `make db-up && make migrate` (no new migrations from this feature, but the meta-runner
  must still be current)
- `make dev` running (`ze-api` on `:8000`)
- A single conversation thread (`thread_id`) with an active session

## Scenario 1 — Compaction triggers and recovers a fact from before the compaction point (US1, SC-001/SC-002)

1. Send enough turns on one thread to push accumulated history past 70% of the routed
   model's context window (`ze_core/openrouter/context_windows.py:get_context_window`
   for that model). The eval harness (`eval/run.py`) is the repeatable way to do this —
   add/point at a scenario under `eval/scenarios/` that scripts a long thread with a
   planted fact early on (e.g. "my flight number is ZE482") followed by enough filler
   turns to force compaction.
2. Ask a question that requires recalling the planted fact.
3. **Expected**: the turn completes without a context-capacity error, and the reply
   correctly reflects the planted fact (see contracts/trace-schema.md — inspect that
   turn's `GET /api/v0/messages/{id}/trace` and confirm `compaction.span_end` covers the
   planted-fact message's index).
4. Repeat steps 1–3 letting the thread grow further — confirm a second compaction
   happens (FR-004, US1 scenario 2) — `compaction.span_end` on the later turn should be
   greater than on the first.

## Scenario 2 — Resume recap surfaces outstanding state silently (US2)

1. Create at least one of: an active `OpenLoop`, an in-flight goal, an in-flight
   workflow (any existing flow — e.g. let the goal engine start a multi-week goal).
2. Let the thread go idle past `session_inactivity_minutes` (config value shared with
   `SessionSummariser`, `core/ze-memory/ze_memory/session_summary.py`) — or lower that
   config value temporarily in a test `config.yaml` to speed up validation.
3. Send a new message on the same thread that does *not* mention the outstanding item.
4. **Expected**: no separate "welcome back" WS frame or chat bubble appears (FR-007a);
   the assistant's reply content reflects the outstanding item; that turn's trace shows
   `resume_recap_applied: true`.
5. Repeat with no outstanding open loops/goals/workflows — expect a normal reply with
   `resume_recap_applied: false` and no fabricated recap content (FR-008).
6. Repeat with a gap shorter than the threshold — expect `resume_recap_applied: false`
   (FR-009).

## Scenario 3 — Trace transparency (US3)

1. After Scenario 1's compacted turn, call
   `GET /api/v0/messages/{id}/trace` for that message id.
2. **Expected**: response includes `compaction: {span_start, span_end}` per
   contracts/trace-schema.md.

## Scenario 4 — Failure fallback (edge case, FR-010)

1. In a test/dev environment, force the compaction-summarization LLM call to fail
   (e.g. temporarily point the OpenRouter client at an invalid model for that call, or
   use the existing mock-`client.complete` test pattern in an integration test rather
   than live dev).
2. **Expected**: the turn still completes (hard-trim fallback, research.md R7); no
   500/timeout surfaced to the user.

## Scenario 5 — Unknown model fallback (edge case, FR-005)

1. Route a turn to a model not present in `MODEL_CONTEXT_WINDOWS`.
2. **Expected**: `get_context_window` returns `DEFAULT_CONTEXT_WINDOW_TOKENS`, the
   turn proceeds without error (SC-005).

## Automated coverage

- Unit tests: `make test-core` (covers `core/ze-core/tests/orchestration/nodes/
  test_context_budget.py`, `test_resume_recap.py`, `test_context_windows.py`).
- Eval suite (SC-002 recall accuracy): `python eval/run.py --tag session-continuity`
  once scenarios are added under `eval/scenarios/`.
