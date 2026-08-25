# Quickstart: Validating Usage Dashboard Charts

## Prerequisites

- `make dev-full` running, with at least 30 days of cost data (real usage or seeded).

## 1. Validate the spend trend chart (User Story 1)

1. Open `/costs`.
2. Confirm the top chart is the new chart component (not the old bar-row `SpendChart`), with per-day values inspectable via hover/focus.
3. Confirm a day with zero spend within the 30-day window still shows as a zero-height bar/point, not a gap.

## 2. Validate the breakdown charts (User Story 2)

1. Confirm the "By plugin" panel shows a chart (pie or bar) of relative spend share, above the existing per-plugin numeric list.
2. Confirm the "By agent" panel shows the equivalent.
3. Confirm both existing lists (percentage, call count, token count, cost/call) are still present and unchanged.

## 3. Validate visual consistency (User Story 3)

- `rtk proxy grep -n "#[0-9a-fA-F]\{3,6\}\|rgba(" apps/ze-web/src/widgets/costs-overview/ui/*.tsx` — confirm no hardcoded hex/rgba color remains outside token-driven Tailwind classes (SC-003).
- Compare page chrome (panels, stat cards) against the memory-graph page (post spec-119) for consistent tokens.

## 4. Validate edge cases

- A fresh account with 1 day of spend — chart must render sensibly, not a broken 30-day axis.
- Zero total spend for the period — chart shows a clear "no spend yet" state.
- 10+ plugins with spend — breakdown chart stays legible (grouped/truncated, not unreadable).
- Narrow viewport — all charts remain legible.
