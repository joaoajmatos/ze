# Contract: None

This feature introduces no backend/API changes. `GET /api/v0/data/domains` (`useDataDomainsQuery`) already returns every field the new charts need (`name`, `size_bytes`, `count`, `importable`). This is a pure frontend rework — `StorageDonutChart` is replaced and the "By domain" breakdown gains a chart; the data layer and its existing `lib/aggregate.ts`/`lib/format.ts` helpers do not change their contracts.
