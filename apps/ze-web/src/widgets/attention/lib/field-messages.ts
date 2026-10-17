type ValidationDetail = { loc: (string | number)[]; msg: string };

/** Maps FastAPI 422 `detail[]` entries to a field name → message map. */
export function fieldMessages(error: unknown): Record<string, string> {
  const detail = (error as { detail?: ValidationDetail[] } | undefined)?.detail;
  if (!Array.isArray(detail)) return {};
  const out: Record<string, string> = {};
  for (const entry of detail) {
    const field = entry.loc[entry.loc.length - 1];
    if (typeof field === "string") out[field] = entry.msg;
  }
  return out;
}
