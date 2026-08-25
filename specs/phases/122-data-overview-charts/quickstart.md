# Quickstart: Validating Data Overview Charts

## Prerequisites

- `make dev-full` running, with data spread across at least 3 domain categories (real usage or seeded).

## 1. Validate the category chart (User Story 1)

1. Open `/data`.
2. Confirm "By category" renders using the new chart component (not the old hand-rolled SVG donut), with each category's exact value inspectable.
3. Confirm a single-category account still renders sensibly.
4. Confirm a zero-data account shows a clear empty state.

## 2. Validate the domain comparison chart (User Story 2)

1. Expand a category group with 3+ domains of differing sizes.
2. Confirm a chart shows their relative size, with the existing per-domain numeric detail (bytes, record count, importable badge) still present.
3. Confirm a domain with zero size within the group renders as zero/absent, not broken.

## 3. Validate edge cases

- Zero total storage — category chart shows a clear empty state, not a misleading full/broken chart.
- Many categories/domains — chart stays legible (existing "other" bucketing / chart-level truncation).
- Narrow viewport — both charts remain legible.

## 4. Validate no hardcoded colors remain

```bash
rtk proxy grep -n "#[0-9a-fA-F]\{3,6\}\|rgba(" apps/ze-web/src/widgets/data-overview/**/*.tsx
```

Confirm no chart-related hardcoded color remains outside token-driven Tailwind classes (SC-003).
