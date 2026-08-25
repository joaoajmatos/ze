"use client";

import { ParentSize } from "@visx/responsive";
import { type ReactNode, useMemo, useState } from "react";
import { cn } from "../lib/cn";
import { weekdayDateFmt } from "./chart-formatters";
import { pointsToHeatmapGrid, type HeatmapCell, type HeatmapPoint } from "./heatmap-data";

const LEVEL_COLORS = [
  "var(--chart-scale-01)",
  "var(--chart-scale-02)",
  "var(--chart-scale-03)",
  "var(--chart-scale-04)",
  "var(--chart-scale-05)",
] as const;

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MONTH_FMT = new Intl.DateTimeFormat("en-US", { month: "short" });

export interface ZeHeatmapChartProps {
  data: HeatmapPoint[];
  title?: string;
  className?: string;
  /** First row of the grid. 0 = Sunday, 1 = Monday. Default: 1 */
  weekStartDay?: number;
  formatLabel?: (value: number, date: Date) => string;
  renderTooltip?: (cell: HeatmapCell) => ReactNode;
}

function defaultLabel(value: number, date: Date): string {
  return `${weekdayDateFmt.format(date)} · ${value}`;
}

export function HeatmapChart({
  data,
  title,
  className,
  weekStartDay = 1,
  formatLabel = defaultLabel,
  renderTooltip,
}: ZeHeatmapChartProps) {
  const grid = useMemo(() => pointsToHeatmapGrid(data, weekStartDay), [data, weekStartDay]);
  const [hovered, setHovered] = useState<HeatmapCell | null>(null);

  if (grid.columns === 0) {
    return (
      <div className="flex h-40 w-full items-center justify-center rounded-[20px] border border-white/10 bg-white/[0.02] text-xs text-smoke">
        {title ? `${title} — no data` : "No data"}
      </div>
    );
  }

  const monthLabels = grid.cells
    .filter((cell) => cell.row === 0 && cell.date.getDate() <= 7)
    .reduce<{ col: number; label: string }[]>((acc, cell) => {
      const label = MONTH_FMT.format(cell.date);
      if (acc.some((item) => item.label === label && cell.col - item.col < 3)) return acc;
      acc.push({ col: cell.col, label });
      return acc;
    }, []);

  return (
    <div className={cn("w-full", className)}>
      {title && (
        <p className="mb-2 text-xs font-semibold tracking-widest uppercase text-smoke">
          {title}
        </p>
      )}
      <ParentSize debounceTime={10}>
        {({ width }) => {
          if (width <= 0) return null;
          const labelWidth = 28;
          const gap = 3;
          const available = Math.max(width - labelWidth, 80);
          const binSize = Math.max(8, Math.min(14, (available - gap * (grid.columns - 1)) / grid.columns));
          const plotWidth = grid.columns * binSize + (grid.columns - 1) * gap;
          const plotHeight = 7 * binSize + 6 * gap;
          const header = 18;

          return (
            <div className="relative" style={{ width: labelWidth + plotWidth, height: header + plotHeight }}>
              {monthLabels.map((item) => (
                <span
                  className="absolute text-[10px] text-chart-label"
                  key={`${item.label}-${item.col}`}
                  style={{ left: labelWidth + item.col * (binSize + gap), top: 0 }}
                >
                  {item.label}
                </span>
              ))}
              {WEEKDAY_LABELS.map((label, row) =>
                row % 2 === 0 ? (
                  <span
                    className="absolute text-[10px] text-chart-label"
                    key={label}
                    style={{
                      left: 0,
                      top: header + row * (binSize + gap) + binSize / 2,
                      transform: "translateY(-50%)",
                    }}
                  >
                    {label}
                  </span>
                ) : null,
              )}
              <svg
                width={plotWidth}
                height={plotHeight}
                className="absolute"
                style={{ left: labelWidth, top: header }}
                onMouseLeave={() => setHovered(null)}
              >
                {grid.cells.map((cell) => (
                  <rect
                    key={cell.iso}
                    x={cell.col * (binSize + gap)}
                    y={cell.row * (binSize + gap)}
                    width={binSize}
                    height={binSize}
                    rx={2}
                    fill={LEVEL_COLORS[cell.level]}
                    onMouseEnter={() => setHovered(cell)}
                  />
                ))}
              </svg>
              {hovered && (
                <div
                  className="pointer-events-none absolute z-10 rounded-lg border border-white/10 bg-black/90 px-2.5 py-2 text-[11px] text-smoke shadow-xl"
                  style={{
                    left: labelWidth + hovered.col * (binSize + gap) + binSize / 2,
                    top: header + hovered.row * (binSize + gap) - 8,
                    transform: "translate(-50%, -100%)",
                  }}
                >
                  {renderTooltip ? renderTooltip(hovered) : formatLabel(hovered.value, hovered.date)}
                </div>
              )}
            </div>
          );
        }}
      </ParentSize>
      <div className="mt-2 flex items-center justify-end gap-1.5 text-[10px] text-smoke">
        <span>Less</span>
        {LEVEL_COLORS.map((color) => (
          <span
            className="inline-block rounded-[2px]"
            key={color}
            style={{ width: 11, height: 11, backgroundColor: color }}
          />
        ))}
        <span>More</span>
      </div>
    </div>
  );
}
