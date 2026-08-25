import type { ActivityHeatmapResponse } from "@myguyze/ze-client";
import { HeatmapChart } from "@myguyze/ze-ui/charts";
import { DayDetailPopover } from "./DayDetailPopover";

interface Props {
  data: ActivityHeatmapResponse;
}

function isoDay(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function activitySeries(data: ActivityHeatmapResponse): { x: string; y: number }[] {
  const totals = new Map(data.days.map((day) => [day.date, day.total]));
  const points: { x: string; y: number }[] = [];
  const cursor = new Date(`${data.start}T00:00:00`);
  const end = new Date(`${data.end}T00:00:00`);
  while (cursor <= end) {
    const x = isoDay(cursor);
    points.push({ x, y: totals.get(x) ?? 0 });
    cursor.setDate(cursor.getDate() + 1);
  }
  return points;
}

export function AgentHeatmap({ data }: Props) {
  return (
    <HeatmapChart
      data={activitySeries(data)}
      formatLabel={(value, date) =>
        `${date.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })} · ${value} messages`
      }
      renderTooltip={(cell) => {
        const day = data.days.find((item) => item.date === cell.iso);
        if (!day) {
          return (
            <p>
              {cell.date.toLocaleDateString("en-US", { month: "short", day: "numeric" })} · 0
            </p>
          );
        }
        return <DayDetailPopover day={day} />;
      }}
    />
  );
}
