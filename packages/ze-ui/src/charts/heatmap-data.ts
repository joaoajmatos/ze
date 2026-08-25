export interface HeatmapPoint {
  x: string;
  y: number;
}

export interface HeatmapCell {
  date: Date;
  iso: string;
  value: number;
  level: 0 | 1 | 2 | 3 | 4;
  row: number;
  col: number;
}

export interface HeatmapGrid {
  cells: HeatmapCell[];
  columns: number;
  rows: 7;
}

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

export function parseIsoDay(iso: string): Date {
  return new Date(`${iso}T00:00:00`);
}

export function toIsoDay(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function contributionLevel(value: number, max: number): 0 | 1 | 2 | 3 | 4 {
  if (value <= 0 || max <= 0) return 0;
  const t = value / max;
  if (t <= 0.25) return 1;
  if (t <= 0.5) return 2;
  if (t <= 0.75) return 3;
  return 4;
}

function startOfWeek(date: Date, weekStartDay: number): Date {
  const result = new Date(date);
  const delta = (result.getDay() - weekStartDay + 7) % 7;
  result.setDate(result.getDate() - delta);
  result.setHours(0, 0, 0, 0);
  return result;
}

/** Build a Monday-first (by default) week-column grid from ChartPoint dates. */
export function pointsToHeatmapGrid(
  data: HeatmapPoint[],
  weekStartDay = 1,
): HeatmapGrid {
  const byIso = new Map<string, number>();
  for (const point of data) {
    if (!ISO_DAY.test(point.x)) continue;
    byIso.set(point.x, (byIso.get(point.x) ?? 0) + point.y);
  }

  const dates = [...byIso.keys()].sort();
  if (dates.length === 0) {
    return { cells: [], columns: 0, rows: 7 };
  }

  const first = startOfWeek(parseIsoDay(dates[0]), weekStartDay);
  const last = parseIsoDay(dates[dates.length - 1]);
  const end = new Date(last);
  const endDelta = (weekStartDay + 6 - end.getDay() + 7) % 7;
  end.setDate(end.getDate() + endDelta);

  const max = Math.max(...byIso.values(), 0);
  const cells: HeatmapCell[] = [];
  const cursor = new Date(first);
  let col = 0;

  while (cursor <= end) {
    for (let row = 0; row < 7; row += 1) {
      const iso = toIsoDay(cursor);
      const value = byIso.get(iso) ?? 0;
      cells.push({
        date: new Date(cursor),
        iso,
        value,
        level: contributionLevel(value, max),
        row,
        col,
      });
      cursor.setDate(cursor.getDate() + 1);
    }
    col += 1;
  }

  return { cells, columns: col, rows: 7 };
}
