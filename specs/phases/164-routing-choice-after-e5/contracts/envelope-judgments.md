# Contract: Envelope, confidence and trace rows

## `route()` signature

```python
async def route(self, prompt: str, session_id: str, *, judgment_state: dict | None = None) -> RoutingEnvelope
```

`prompt` stays the combined E5 text. `judgment_state` is `None` when the caller has no named parts (existing tests, API callers): the router then makes no System One call (160 path).

## Envelope semantics

| Outcome | `is_compound` | `confidence` | `score_gap` | `raw_scores` | `primary_agent` | `complexity` |
|---|---|---|---|---|---|---|
| skip / abstain | per 160 bars | cosine | cosine gap | cosine | E5 top | regex |
| trust | `False` | Choice peakedness | cosine gap | cosine | Choice agent | Score level if consumed else regex |
| decompose | `True` | Choice peakedness | cosine gap | cosine | E5 top | Score level if consumed else regex |

`complexity_source` is `"score"` when the Score level was consumed. `envelope.judgment` is set whenever a request was attempted (ok or skip).

## `decompose` node

If the incoming envelope has `complexity_source == "score"`, the node keeps `complexity` for the primary subtask and sets subtask models with `_resolve_model`; otherwise it calls `classify` as today. `apply_conductor_rewrite` is untouched.

## Trace rows

`embed_route` converts `envelope.judgment` with `judgments_from_result` and returns them as `state["judgments"]` (reset each turn at `turn.py:63`, copied by `record_trace`). Row `consumed` is true for ids in the decision's consumed set.

`judgments_from_result` signature change (hard cut):

```python
def judgments_from_result(result, *, question_kinds: Mapping[str, str], consumed, skip_reason=None) -> list[JudgmentTrace]
```

- Skip rows take `kind` from `question_kinds[qid]` (so Score rows are `score`).
- Missing-answer rows take `kind` from `question_kinds[qid]`.
- Rows with an answer keep `answer.type`.
- `Score` rows: `answer` = the float, `peakedness=None`, `probabilities=None`.
- The 163 caller passes `{qid: SPEECH_ACT_QUESTIONS[qid].type for qid in admission.question_ids}`.

## Persistence

No new column. `routing_log.confidence` is peakedness when a Choice is consumed; read it together with `method`. `MessageTrace.confidence` follows the envelope.
