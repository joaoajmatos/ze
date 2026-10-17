import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { presenceActions, usePresenceStore } from "@/entities/presence";
import { useNarrow, useReducedMotion } from "@/shared/lib";
import { usePaletteColors, type OrbColors } from "@/shared/ui";
import type { OrbState } from "./model/hud";

interface Ctx {
  palette: string;
  /** The orb state the views drive for the demo; attention, acting and assembling reach the real orb. */
  orb: OrbState;
  setOrb: (s: OrbState) => void;
  reducedMotion: boolean;
  /** Phone-width layout. */
  narrow: boolean;
  colors: OrbColors;
}

const JarvisCtx = createContext<Ctx | null>(null);
export function useJarvis(): Ctx {
  const c = useContext(JarvisCtx);
  if (!c) throw new Error("useJarvis outside JarvisShell");
  return c;
}

const WORLD_SIGNALS = new Set<OrbState>(["attention", "acting", "assembling"]);

/** The context the prototype views read. The chrome is the real shell's. */
export function JarvisShell({ children }: { children: ReactNode }) {
  const [orb, setOrb] = useState<OrbState>(() => usePresenceStore.getState().presence.orb);
  const reducedMotion = useReducedMotion();
  const narrow = useNarrow();
  const colors = usePaletteColors();
  const palette = document.documentElement.dataset.palette ?? "orchid";

  useEffect(() => {
    presenceActions.setWorldSignal(WORLD_SIGNALS.has(orb) ? (orb as "attention" | "acting" | "assembling") : null);
    return () => presenceActions.setWorldSignal(null);
  }, [orb]);

  const ctx = useMemo<Ctx>(() => ({ palette, orb, setOrb, reducedMotion, narrow, colors }), [palette, orb, reducedMotion, narrow, colors]);
  return <JarvisCtx.Provider value={ctx}>{children}</JarvisCtx.Provider>;
}
