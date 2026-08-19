import type { ReactNode } from "react";
import { Area } from "./area";
import { AreaChart as BklitAreaChart } from "./area-chart";
import { Bar } from "./bar";
import { BarChart as BklitBarChart } from "./bar-chart";
import { BarXAxis } from "./bar-x-axis";
import { Grid } from "./grid";
import { Line } from "./line";
import { LineChart as BklitLineChart } from "./line-chart";
import { PieChart as BklitPieChart } from "./pie-chart";
import { PieSlice } from "./pie-slice";
import { ChartTooltip } from "./tooltip";
import { XAxis } from "./x-axis";

/**
 * Ze's chart data contract — mirrors core/ze-components' `ChartPoint` dataclass
 * (see specs/phases/118-chart-visualization/data-model.md) so agent-emitted and
 * hand-placed charts share one shape.
 */
export interface ChartPoint {
  x: string;
  y: number;
  series?: string;
}

export interface ZeChartProps {
  data: ChartPoint[];
  seriesLabels?: Record<string, string>;
  xLabel?: string;
  yLabel?: string;
  title?: string;
  legend?: boolean;
  className?: string;
}

const SERIES_COLOR_VARS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

const IMPLICIT_SERIES = "value";

function seriesNames(data: ChartPoint[]): string[] {
  const names = new Set<string>();
  for (const point of data) {
    names.add(point.series ?? IMPLICIT_SERIES);
  }
  return Array.from(names);
}

function colorFor(index: number): string {
  return SERIES_COLOR_VARS[index % SERIES_COLOR_VARS.length];
}

/** Parses a ChartPoint's pre-formatted x label into a Date for time-series charts.
 * Falls back to an index-spaced synthetic date when x isn't parseable, so ordering
 * is preserved even for non-date category labels (a known limitation — line/area
 * charts in this library are time-series-shaped, see research.md R1 follow-up). */
function toTimeSeriesRows(
  data: ChartPoint[],
  series: string[]
): Record<string, unknown>[] {
  const byX = new Map<string, Record<string, unknown>>();
  const order: string[] = [];
  data.forEach((point, i) => {
    const key = point.x;
    if (!byX.has(key)) {
      byX.set(key, {});
      order.push(key);
    }
    const row = byX.get(key)!;
    row[point.series ?? IMPLICIT_SERIES] = point.y;
    row.__index = i;
  });
  return order.map((key, i) => {
    const row = byX.get(key)!;
    const parsed = new Date(key);
    const date = Number.isNaN(parsed.getTime())
      ? new Date(2000, 0, 1 + i)
      : parsed;
    for (const s of series) {
      if (!(s in row)) row[s] = undefined;
    }
    return { ...row, date, label: key };
  });
}

function toCategoryRows(
  data: ChartPoint[],
  series: string[]
): Record<string, unknown>[] {
  const byX = new Map<string, Record<string, unknown>>();
  const order: string[] = [];
  for (const point of data) {
    if (!byX.has(point.x)) {
      byX.set(point.x, { name: point.x });
      order.push(point.x);
    }
    byX.get(point.x)![point.series ?? IMPLICIT_SERIES] = point.y;
  }
  return order.map((key) => {
    const row = byX.get(key)!;
    for (const s of series) {
      if (!(s in row)) row[s] = undefined;
    }
    return row;
  });
}

function ChartFrame({
  title,
  xLabel,
  yLabel,
  children,
}: {
  title?: string;
  xLabel?: string;
  yLabel?: string;
  children: ReactNode;
}) {
  return (
    <div className="w-full">
      {title && (
        <p className="mb-2 text-xs font-semibold tracking-widest uppercase text-smoke">
          {title}
        </p>
      )}
      {children}
      {(xLabel || yLabel) && (
        <div className="mt-1 flex justify-between text-[11px] text-smoke">
          <span>{yLabel}</span>
          <span>{xLabel}</span>
        </div>
      )}
    </div>
  );
}

function EmptyChart({ title }: { title?: string }) {
  return (
    <div className="flex h-40 w-full items-center justify-center rounded-[20px] border border-white/10 bg-white/[0.02] text-xs text-smoke">
      {title ? `${title} — no data` : "No data"}
    </div>
  );
}

export function LineChart({
  data,
  seriesLabels,
  xLabel,
  yLabel,
  title,
  className,
}: ZeChartProps) {
  if (data.length === 0) return <EmptyChart title={title} />;
  const series = seriesNames(data);
  const rows = toTimeSeriesRows(data, series);
  return (
    <ChartFrame title={title} xLabel={xLabel} yLabel={yLabel}>
      <BklitLineChart className={className} data={rows} xDataKey="date">
        <Grid />
        <XAxis />
        {series.map((s, i) => (
          <Line dataKey={s} key={s} stroke={colorFor(i)} />
        ))}
        <ChartTooltip />
      </BklitLineChart>
      {series.length > 1 && (
        <Legend names={series} labels={seriesLabels} />
      )}
    </ChartFrame>
  );
}

export function AreaChart({
  data,
  seriesLabels,
  xLabel,
  yLabel,
  title,
  className,
}: ZeChartProps) {
  if (data.length === 0) return <EmptyChart title={title} />;
  const series = seriesNames(data);
  const rows = toTimeSeriesRows(data, series);
  return (
    <ChartFrame title={title} xLabel={xLabel} yLabel={yLabel}>
      <BklitAreaChart className={className} data={rows} xDataKey="date">
        <Grid />
        <XAxis />
        {series.map((s, i) => (
          <Area dataKey={s} fill={colorFor(i)} key={s} />
        ))}
        <ChartTooltip />
      </BklitAreaChart>
      {series.length > 1 && (
        <Legend names={series} labels={seriesLabels} />
      )}
    </ChartFrame>
  );
}

export function BarChart({
  data,
  seriesLabels,
  xLabel,
  yLabel,
  title,
  className,
}: ZeChartProps) {
  if (data.length === 0) return <EmptyChart title={title} />;
  const series = seriesNames(data);
  const rows = toCategoryRows(data, series);
  return (
    <ChartFrame title={title} xLabel={xLabel} yLabel={yLabel}>
      <BklitBarChart className={className} data={rows} xDataKey="name">
        <Grid />
        <BarXAxis />
        {series.map((s, i) => (
          <Bar dataKey={s} fill={colorFor(i)} key={s} />
        ))}
        <ChartTooltip />
      </BklitBarChart>
      {series.length > 1 && (
        <Legend names={series} labels={seriesLabels} />
      )}
    </ChartFrame>
  );
}

export function PieChart({ data, seriesLabels, title, className }: ZeChartProps) {
  if (data.length === 0) return <EmptyChart title={title} />;
  const slices = data.map((point, i) => ({
    label: seriesLabels?.[point.x] ?? point.x,
    value: point.y,
    color: colorFor(i),
  }));
  return (
    <ChartFrame title={title}>
      <BklitPieChart className={className} data={slices}>
        {slices.map((slice, i) => (
          <PieSlice index={i} key={slice.label} />
        ))}
      </BklitPieChart>
    </ChartFrame>
  );
}

function Legend({
  names,
  labels,
}: {
  names: string[];
  labels?: Record<string, string>;
}) {
  return (
    <div className="mt-2 flex flex-wrap gap-3">
      {names.map((name, i) => (
        <span
          className="flex items-center gap-1.5 text-[11px] text-smoke"
          key={name}
        >
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: colorFor(i) }}
          />
          {labels?.[name] ?? name}
        </span>
      ))}
    </div>
  );
}
