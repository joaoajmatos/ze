/** Humanize a raw enum-style status value, e.g. "awaiting_gate" -> "Awaiting gate". */
export function humanizeStatus(status: string): string {
  const spaced = status.replace(/_/g, " ").trim();
  if (!spaced) return spaced;
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/**
 * Humanize a raw snake_case/kebab-case identifier used as a fallback display
 * name (e.g. "lembrete_regar_plantas" -> "Lembrete regar plantas"). Leaves
 * names that already look human-authored (contain a space, or aren't purely
 * snake/kebab-case) untouched.
 */
export function humanizeIdentifier(name: string): string {
  const looksRaw = /^[a-z0-9]+([_-][a-z0-9]+)+$/.test(name);
  if (!looksRaw) return name;
  const spaced = name.replace(/[_-]/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
