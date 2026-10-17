export type PaletteId = "orchid" | "ultraviolet" | "amethyst";

export const PALETTE_IDS: readonly PaletteId[] = ["orchid", "ultraviolet", "amethyst"];

const STORAGE_KEY = "ze.palette";

function isPaletteId(value: unknown): value is PaletteId {
  return PALETTE_IDS.includes(value as PaletteId);
}

export function readPalette(): PaletteId {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return isPaletteId(stored) ? stored : "orchid";
  } catch {
    return "orchid";
  }
}

export function applyPalette(id: PaletteId): void {
  document.documentElement.dataset.palette = id;
}

export function storePalette(id: PaletteId): void {
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    // Storage blocked: the choice lasts until reload.
  }
}
