/** Scales `values` into SVG coordinates: min at the bottom, max at the top, zero-range flat at the baseline. */
export function seriesPoints(values: readonly number[], width: number, height: number): [number, number][] {
  if (values.length === 0) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min;
  return values.map((v, i) => {
    const x = values.length === 1 ? width / 2 : 1 + (i / (values.length - 1)) * (width - 2);
    const y = span === 0 ? height - 1 : height - 1 - ((v - min) / span) * (height - 2);
    return [x, y];
  });
}

/** A series as a tiny line. `Spark` draws a two-point change; this draws N points. */
export function SeriesSpark({ values, label, format = String, width = 160, height = 20 }: { values: readonly number[]; label: string; format?: (n: number) => string; width?: number; height?: number }) {
  const pts = seriesPoints(values, width, height);
  const aria = values.length
    ? `${label}: first ${format(values[0])}, last ${format(values[values.length - 1])}, max ${format(Math.max(...values))}`
    : `${label}: no data`;
  return (
    <svg className="spark" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={aria}>
      <line x1={1} x2={width - 1} y1={height - 1} y2={height - 1} className="spark-base" />
      {pts.length > 0 && <polyline points={pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ")} className="spark-line" />}
      {pts.length > 0 && <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r={1.8} className="spark-dot" />}
    </svg>
  );
}
