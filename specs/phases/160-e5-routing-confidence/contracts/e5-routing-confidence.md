# Contract: E5 routing confidence

Identifiers: `ROUTING_THRESHOLD`, `ROUTING_GAP`, `intfloat/multilingual-e5-base`, `is_compound`, `decompose`, `query:`, `passage:`.

## Shipped (do not regress)

- `E5Embedder.encode_query` / `encode_passage` prefixes
- Shared singleton for routing + memory
- Haiku `decompose` node when `is_compound`
- `apply_conductor_rewrite` sequential/mixed rules (153/155)

## 160 must change

| Leak | Required |
|---|---|
| `ROUTING_THRESHOLD = 0.55`, `ROUTING_GAP_THRESHOLD = 0.10` | E5-calibrated pair in `ze_agents.defaults` |
| YAML-only `gap_threshold: 0.03` | Defaults and YAML agree; no YAML → still E5 bars |
| Constitution VII / ADR / AGENTS stack table name MiniLM | Name `intfloat/multilingual-e5-base` |

## Forbidden

- Restore MiniLM as the live model
- Delete `decompose`
- Edit 153/155 rewrite predicates
- Second embedder for routing vs memory
