# Contract: Language-Neutral "What's Open" Detection (171)

## `OpenQueryDetector` (new, `ze_priority/open_query.py`)

```python
OPEN_QUERY_THRESHOLD: float   # set from calibration (research.md Verdict)
OPEN_QUERY_EXAMPLES: tuple[str, ...]   # ~15 EN + ~15 PT

class OpenQueryDetector:
    def __init__(self, embedder: Any, *, examples: Sequence[str] = OPEN_QUERY_EXAMPLES,
                 threshold: float = OPEN_QUERY_THRESHOLD) -> None: ...
    def best_similarity(self, embedding: Any) -> float: ...   # max cosine; raises on embedder error
    def is_open_query(self, embedding: Any) -> bool: ...      # False on any error (warning logged)
```

- Examples are embedded once, on first use, with `embedder.encode(list(examples))` — the same method (and `passage:` prefix) `fetch_context` uses for the prompt. Vectors are L2-normalised; cosine is a dot product.
- `embedding is None` → `False`.
- Starting EN examples (the ENG lead may refine on the tuned set only): "what's open", "what's still open for me", "what's outstanding", "what's on my plate", "what am I still sitting with", "what do I still need to deal with", "what's pending", "anything I'm forgetting", "what loose ends do I have", "what's left on my list".
- Starting PT examples: "o que tenho em aberto", "o que está pendente", "o que me falta tratar", "o que ainda tenho para resolver", "tenho alguma coisa pendente", "o que está no meu prato", "o que ficou por fazer", "de que é que me estou a esquecer", "que pontas soltas tenho", "o que ainda está em aberto".

## `TurnSurfacing` changes

```python
def __init__(self, priority_view, override_store, graph_store, loop_store, embedder, push_log=None,
             open_query_detector: OpenQueryDetector | None = None) -> None
def is_global_open_query(self, embedding: Any) -> bool   # instance method now; delegates to the detector
```

The detector defaults to `OpenQueryDetector(embedder)`. `_GLOBAL_OPEN_RE` and the static method are deleted.

## Calibration files

`eval/calibration/open_query.jsonl` and `open_query_holdout.jsonl`, one JSON object per line:

```json
{"id": "oq-en-pos-01", "lang": "en", "text": "What's still on my plate this week?", "label": true}
{"id": "oq-pt-neg-07", "lang": "pt", "text": "A farmácia está aberta ao domingo?", "label": false}
```

`id` unique across both files; no text appears in both files; held-out written before the first tuned run.

## Script `eval/calibration/open_query.py`

| Mode | Behavior |
|---|---|
| `--check-sets` | shape, unique ids, no overlap, counts per lang/label; exit 1 on violation |
| `--set tuned` (default) | real E5; per-language recall and FPR across thresholds 0.80–0.95 step 0.005; prints the suggested threshold (lowest with tuned FPR ≤ 0.02 in both languages) |
| `--set holdout --threshold T` | single verdict; PASS iff recall ≥ 0.90 and FPR ≤ 0.05 for each language; prints misclassified ids |

`make calibrate-open-query ARGS="..."` runs it with `uv run`. Never collected by pytest. No network beyond the local model files.
