/** Claim-kind glyph, the same vocabulary as the field marks: filled told, half inferred, dashed suspected, hollow goal. */
export function Glyph({ kind, hot = false }: { kind: "told" | "inferred" | "suspected" | "goal"; hot?: boolean }) {
  return <i className={`glyph ${kind} ${hot ? "hot" : ""}`} aria-hidden="true" />;
}
