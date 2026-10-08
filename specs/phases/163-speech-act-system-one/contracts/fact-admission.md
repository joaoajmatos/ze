# Contract: Fact admission → write_memory → trace

**Feature**: `163-speech-act-system-one`

## `gather_fact_proposals` (hard cut)

```python
async def gather_fact_proposals(
    configurable: dict, *, agent: str, prompt: str, response: str
) -> FactAdmission
```

Flow:
1. No `openrouter_client`, a trivial turn, or a response starting with `[ERROR]`: return `FactAdmission(facts=[], path="none")`.
2. Read `speech_act_surface_config(configurable["settings"])`. If the surface is not enabled, or there is no `system_one_client` in `configurable`, run the pre-163 Haiku judge (`extract_facts`) and return `path="haiku"`. If the surface is enabled but uncalibrated, log a warning, run the Haiku judge, and return `path="haiku"` with `skip_reason="uncalibrated"`.
3. Call the client once (`max_attempts=1`) and `decide()`.
   - `skip` → run the Haiku judge once. Return `path="haiku"`, `judgment=result` and `consumed=∅`.
   - `hold` → `facts=[]` with **no** `complete` call. Return `path="system_one"`.
   - `persist(family)` → run the value writer once (`_VALUE_SYSTEM`, `max_tokens=200`, same model as `fact_extraction_model`). Parse `{"facts":[{"value":…}]}`. Each value becomes `Fact(predicate=family, value=…, confidence=0.8)`. A parse failure or empty list means `facts=[]`. Return `path="system_one"`.
4. Set `fact.agent = agent` on every fact.

The value writer's output has no `speech_act` or `family` key. If one appears, it is ignored. A value-writer exception is logged and treated as `facts=[]`, with no fallback judge.

## `write_memory` (ze-core)

- The `eval-` skip is unchanged: no extractor call.
- `admission = await fact_extractor(...)`, then `proposals = admission.facts`. The 148 same-turn identity filter and `submit_perception_facts` are unchanged.
- If `admission.judgment is not None` and `state["message_trace"]` is not `None`, compute `rows = judgments_from_result(admission.judgment, question_ids=admission.question_ids, consumed=admission.consumed, skip_reason=admission.skip_reason)` and add `"message_trace": dataclasses.replace(trace, judgments=[*trace.judgments, *rows])` to every return dict, including the compaction branch.
- The debug log `extracted_facts` keeps counting `len(proposals)` and adds `admission_path`.

## Trace surfaces

- The persisted `messages.trace.judgments` and the final `trace_update` frame (both built from `final_state["message_trace"]`) include the rows. Partial streaming frames do not. That is accepted and needs no new frame.
- `JudgmentsSection` (ze-web, 162) renders the rows unchanged. There is no web task.
