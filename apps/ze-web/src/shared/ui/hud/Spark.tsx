/**
 * Confidence over time as a tiny line: from where it stood when last evidenced to where decay has
 * taken it now. A flat line means fresh evidence; a falling one means the claim is ageing.
 */
export function Spark({ from, to, hot = false, dotted = false, label }: { from: number | null; to: number | null; hot?: boolean; dotted?: boolean; label: string }) {
  const W = 46;
  const H = 14;
  const a = from ?? to ?? 0.5;
  const b = to ?? a;
  const pts: string[] = [];
  for (let i = 0; i <= 8; i++) {
    const k = i / 8;
    const v = a + (b - a) * (1 - Math.pow(1 - k, 2));
    pts.push(`${(k * (W - 2) + 1).toFixed(1)},${(H - 1 - v * (H - 2)).toFixed(1)}`);
  }
  return (
    <svg className={`spark ${hot ? "hot" : ""} ${dotted ? "dotted" : ""}`} width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <line x1={1} x2={W - 1} y1={H - 1} y2={H - 1} className="spark-base" />
      <polyline points={pts.join(" ")} className="spark-line" />
      <circle cx={W - 1} cy={H - 1 - b * (H - 2)} r={1.8} className="spark-dot" />
    </svg>
  );
}
