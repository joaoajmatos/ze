# Research: Memory Graph Charts

## R1. Chart source

**Decision**: Reuse the `Chart`/`ChartPoint` primitive and `LineChart`/`BarChart`/`PieChart` components from spec 118-chart-visualization directly (`packages/ze-ui/src/charts`) — both as hand-placed components in `apps/ze-web` widgets (this feature's usage is entirely direct-placement, not agent-emitted SDUI).

**Rationale**: 118 already solved chart sourcing, theming, and the narrow-layout/empty-state requirements this spec also needs (FR-006, FR-008, FR-009 mirror 118's FR-004/FR-006/FR-009). No new chart type is needed — activity-over-time is a `LineChart`/`BarChart` use case, composition is a `PieChart`/`BarChart` use case.

## R2. Per-entity activity data gap

**Finding**: `GET /api/v0/entities/{id}` (`EntityDetailResponse`) returns `facts: FactDigestItem[]` and `episodes: EpisodeDigestItem[]`. `EpisodeDigestItem` has `created_at`; `FactDigestItem` (`apps/ze-api/ze_api/api/schemas.py:165`) does **not** expose a timestamp, even though the underlying `MemoryFact` domain type (`core/ze-memory/ze_memory/types.py`) already has `created_at`.

**Decision**: Add `created_at: datetime` to `FactDigestItem` and populate it from the existing `MemoryFact.created_at` in the entity-detail service — a small, additive backend change, not a new data source. The activity chart (User Story 1) then plots both facts and episodes by `created_at`.

**Alternatives considered**:
- **Episodes-only activity chart** — rejected: silently under-represents activity for entities known mostly through facts (e.g. a topic entity built up from many small facts, few episodes), which would make the chart misleading rather than merely incomplete.

## R3. Graph composition breakdown data

**Finding**: `GraphEntityNode.entity_type` and `GraphEdge.predicate` are already present on every node/edge already loaded into the React Flow graph state (`apps/ze-web/src/widgets/memory-graph/ui/MemoryGraph.tsx`) — nothing server-side is missing.

**Decision**: Compute the composition breakdown (entity-type and/or relation-type proportions) entirely client-side from the graph's current node/edge state, recomputed whenever nodes are added via expand-neighbours (FR-005). No new endpoint or query.

## R4. Placement of the two new charts

**Decision**: Activity chart goes inside `EntityDetailPanel.tsx` (`apps/ze-web/src/widgets/memory-graph/ui/EntityDetailPanel.tsx`), above or alongside the existing Facts/Episodes lists. Composition chart goes in `GraphToolbar.tsx` or a new small panel docked near the toolbar, visible without selecting any entity.

**Rationale**: Matches where the relevant data is already computed/available (`EntityDetailPanel` already receives `detail`; the toolbar/canvas level already has the full node/edge list) — no prop-drilling or new state lifting required.

## R5. Visual consistency pass (User Story 3)

**Finding**: `EntityDetailPanel.tsx` and `GraphSearchBar.tsx`/`GraphToolbar.tsx` already use the app's `--color-foreground`/`--color-smoke` token names (`bg-foreground/[0.03]`, `text-smoke`), consistent with the "Open Sky" system — this page is not as far off-system as the Usage/Data pages were. The main inconsistency is the *absence* of chart-based visualization rather than off-token colors.

**Decision**: User Story 3's scope is narrower than initially assumed — primarily ensuring the two new charts inherit the same tokens (automatic, since they're the shared chart components) and doing a final pass to replace any remaining hardcoded hex/rgba values found during implementation, rather than a full chrome rewrite.
