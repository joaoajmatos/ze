import { LineChart } from "@myguyze/ze-ui/charts";
import { CostsOverview } from "@/widgets/costs-overview";

// Static sample series — proves the starter chart set can be placed directly on a
// dashboard page (spec 118-chart-visualization, User Story 2), independent of any
// agent-emitted rendering path. Wiring this to real daily-spend data is future work.
const SAMPLE_DAILY_SPEND = [
  { x: "Mon", y: 1.2 },
  { x: "Tue", y: 0.8 },
  { x: "Wed", y: 2.1 },
  { x: "Thu", y: 1.5 },
  { x: "Fri", y: 3.0 },
  { x: "Sat", y: 0.4 },
  { x: "Sun", y: 0.9 },
];

export function CostsPage() {
  return (
    <div className="flex flex-col gap-6">
      <CostsOverview />
      <LineChart data={SAMPLE_DAILY_SPEND} title="Daily spend (sample)" yLabel="$" />
    </div>
  );
}
