# Data Model: E5 Routing Confidence

No new tables. No new columns.

| Constant | Module | MiniLM-era | This phase |
|---|---|---|---|
| `ROUTING_THRESHOLD` | `ze_agents.defaults` | 0.55 | E5-calibrated floor (measure; likely nearer the bottom of the 0.73–0.86 band if weak matches must not look confident) |
| `ROUTING_GAP_THRESHOLD` | `ze_agents.defaults` | 0.10 | E5-calibrated gap (YAML already experiments with 0.03) |
| `RouterConfig.threshold` / `gap_threshold` | `ze_core.routing.types` | imports defaults | still imports defaults |
| `models.embedding` | `config.yaml` | already `intfloat/multilingual-e5-base` | unchanged |
| `routing.gap_threshold` / `threshold` | `config.yaml` | gap overlay only | MUST match framework defaults |

`EmbeddingRouter._score_and_route`: `top_score < threshold OR score_gap < gap_threshold` → `is_compound=True` (decompose). Predicate unchanged; numbers change.
