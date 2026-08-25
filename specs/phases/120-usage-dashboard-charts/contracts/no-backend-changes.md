# Contract: None

This feature introduces no backend/API changes. `GET /api/v0/costs/summary` (`useCostsQuery`) and `GET /api/v0/costs/anomalies` (`useCostAnomaliesQuery`) already return every field the new charts need (`by_day`, `by_agent`, `by_plugin`, each with `usd`/`calls`/`tokens`/`prompt_tokens`/`completion_tokens`). This is a pure frontend rework — `SpendChart` and the breakdown panels' rendering change; the data layer does not.
