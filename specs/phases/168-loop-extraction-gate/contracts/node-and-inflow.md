# Contract: node flow and extractor wiring

## write_memory (conversation)
Inside `not is_eval and not is_retry`, after `store.write_episode`:
1. `LoopInflow.admit` applies the trivial-turn skip (decision row 0): no request, no rows, no Haiku, `commit` is `None`.
2. Otherwise `asyncio.gather(fact_extractor(...), loop_admission(configurable, prompt=ctx.prompt))`, each wrapped so an exception becomes the fail-open result for that call.
3. Rows: 163 rows (unchanged) plus, when `admission.judgment` is not `None`, `judgments_from_result(admission.judgment, question_kinds=admission.question_kinds, consumed=admission.consumed, skip_reason=admission.skip_reason)`. One `dataclasses.replace(trace, judgments=[*trace.judgments, *rows])`.
4. If `admission.commit` is not `None`: `fire_and_forget(admission.commit(), label="loop_commit")`.
5. `memory_hooks` loop still runs for plugin hooks; the worldstate conversation hook is no longer in it.

`loop_admission` is `configurable["loop_admission"]`, an async callable built by ze-api from `LoopInflow.admit`. Absent means no loop gate (as an absent `fact_extractor`).

## LoopInflow (ze-worldstate)
Constructor injection: `loop_store`, `graph_store`, `entity_resolver`, `llm_client`, `embedder`, `memory_store`, `collision_store`, `nli_client`, `system_one_client`, `settings`.
- `admit(configurable, *, prompt) -> LoopAdmission` (conversation).
- `extract(text, provenance) -> None` (email, calendar, ingestion): gate, log, commit inline. Same callable signature as today's extractor.
- `commit` for conversation calls `propose_loop_candidates(..., admission=admission)`; a `fallback` admission makes it run the Haiku gate inside the commit (still fire-and-forget).

## Logging (non-conversation)
`log.info("loop_gate_judgment", provenance=..., outcome=..., consumed=[...], answers={qid: noul}, latency_ms=..., skip_reason=...)`.

## Construction sites (all pass client + settings)
`build_container` (ingestion sink, container.py:596), `make_loop_extractor` (messenger, calendar; container.py:833), `ZeContainer._build_config` (adds `loop_admission`, drops the hook). `ze_seed._apply` goes through `build_container`; verify unchanged.

## Trace and UI
Rows use the existing `JudgmentTrace` shape; the trace panel already renders judgments. No REST, WS or `ze-web` change.
