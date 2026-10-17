import type { FocusKind } from "@/shared/lib";

const KINDS: readonly string[] = ["loop", "held_write", "reminder", "hypothesis", "goal"];

export interface Focus {
  kind: FocusKind;
  id: string;
}

/** Parse the `?focus=<kind>:<id>` search param; unknown kinds and malformed values are ignored. */
export function parseFocus(raw: string | null): Focus | null {
  if (!raw) return null;
  const at = raw.indexOf(":");
  if (at <= 0) return null;
  const kind = raw.slice(0, at);
  const id = raw.slice(at + 1);
  if (!id || !KINDS.includes(kind)) return null;
  let decoded = id;
  try {
    decoded = decodeURIComponent(id);
  } catch {
    decoded = id;
  }
  return { kind: kind as FocusKind, id: decoded };
}
