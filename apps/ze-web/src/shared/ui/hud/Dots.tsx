export function Dots({ max, lit, label }: { max: number; lit: number; label: string }) {
  return (
    <span className="dots" role="img" aria-label={label}>
      {Array.from({ length: max }, (_, i) => (
        <i key={i} className={i < lit ? "lit" : ""} />
      ))}
    </span>
  );
}
