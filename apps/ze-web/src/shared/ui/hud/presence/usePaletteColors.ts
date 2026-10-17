import { useEffect, useState } from "react";
import type { OrbColors } from "./types";

function readColors(): OrbColors {
  const cs = getComputedStyle(document.documentElement);
  const get = (name: string, fallback: string) => cs.getPropertyValue(name).trim() || fallback;
  return {
    main: get("--main", "#b9a3ff"),
    cream: get("--cream", "#efe5d7"),
    coral: get("--coral", "#ff6f63"),
    dim: get("--dim", "#9a90ae"),
  };
}

/** The palette's four orb colours, read from the root and refreshed when `data-palette` changes. */
export function usePaletteColors(): OrbColors {
  const [colors, setColors] = useState(readColors);
  useEffect(() => {
    const observer = new MutationObserver(() => setColors(readColors()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-palette"] });
    return () => observer.disconnect();
  }, []);
  return colors;
}
