import { Maximize2, RotateCcw } from "lucide-react";
import { PieChart, type ChartPoint } from "@myguyze/ze-ui/charts";
import { ChartsToggle } from "@/shared/ui";
import { useOptionalCharts } from "@/shared/lib";

const ENTITY_TYPES = ["all", "person", "place", "org", "topic"] as const;
type EntityTypeFilter = (typeof ENTITY_TYPES)[number];

export interface GraphCompositionView {
  byEntityType: ChartPoint[];
  byRelationType: ChartPoint[];
}

interface Props {
  entityType: EntityTypeFilter;
  onEntityTypeChange: (type: EntityTypeFilter) => void;
  onFitView: () => void;
  onResetLayout: () => void;
  composition: GraphCompositionView;
}

export function GraphToolbar({
  entityType,
  onEntityTypeChange,
  onFitView,
  onResetLayout,
  composition,
}: Props) {
  const { chartsVisible, setChartsVisible } = useOptionalCharts("ze.charts.graph");
  const showEntityPie = composition.byEntityType.some((point) => point.y > 0);
  const showRelationPie = composition.byRelationType.some((point) => point.y > 0);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1 rounded-lg border border-foreground/10 p-1">
          {ENTITY_TYPES.map((t) => (
            <button
              key={t}
              onClick={() => onEntityTypeChange(t)}
              className={`px-2 py-1 rounded text-xs capitalize transition-colors ${
                entityType === t
                  ? "bg-plum-voltage/20 text-foreground"
                  : "text-smoke hover:text-foreground"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1 rounded-lg border border-foreground/10 p-1">
          <button
            onClick={onFitView}
            className="p-1 rounded text-smoke hover:text-foreground transition-colors"
            title="Fit view"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onResetLayout}
            className="p-1 rounded text-smoke hover:text-foreground transition-colors"
            title="Reset layout"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>

        <ChartsToggle pressed={chartsVisible} onPressedChange={setChartsVisible} />
      </div>
      {chartsVisible && (showEntityPie || showRelationPie) && (
        <div className="w-64 max-w-[min(16rem,calc(100vw-2rem))] rounded-lg border border-foreground/10 bg-foreground/[0.03] p-3">
          {showEntityPie && <PieChart data={composition.byEntityType} title="Entity types" />}
          {showRelationPie && (
            <div className={showEntityPie ? "mt-3" : undefined}>
              <PieChart data={composition.byRelationType} title="Relation types" />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
