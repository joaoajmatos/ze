import type { WsTraceUpdateFrame } from "@myguyze/ze-client";

export interface MemoryPoint {
  id: number;
  x: number;
  /** Extraction confidence; null sits on the floor line (episodes and profile facets carry none). */
  y: number | null;
  glyph: "fact" | "episode" | "profile" | "other";
  text: string;
  rank: number;
}

const GLYPHS = new Set(["fact", "episode", "profile"]);

/** Points from the live partial or the committed trace; both carry the chunk's extraction confidence. */
export function memoryPoints(chunks: WsTraceUpdateFrame["memory_chunks"] | undefined): { points: MemoryPoint[]; ranked: MemoryPoint[] } {
  const points = (chunks ?? []).map((c, id): MemoryPoint => ({
    id,
    x: c.score,
    y: c.extraction_confidence ?? null,
    glyph: GLYPHS.has(c.source) ? (c.source as MemoryPoint["glyph"]) : "other",
    text: c.text,
    rank: c.score * (c.extraction_confidence ?? 0.5),
  }));
  return { points, ranked: [...points].sort((a, b) => b.rank - a.rank) };
}
