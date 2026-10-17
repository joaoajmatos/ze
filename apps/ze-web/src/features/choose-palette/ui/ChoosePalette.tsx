import { useState } from "react";
import { applyPalette, readPalette, storePalette, type PaletteId } from "@/shared/lib";
import { Control } from "@/shared/ui";

const PALETTES: { id: PaletteId; name: string; note: string }[] = [
  { id: "orchid", name: "Orchid", note: "pale lavender on warm plum" },
  { id: "ultraviolet", name: "Ultraviolet", note: "cool violet on near-black indigo" },
  { id: "amethyst", name: "Amethyst", note: "magenta-leaning purple on violet-black" },
];

/** The palette setting: one choice, applied at once and kept in this browser. */
export function ChoosePalette() {
  const [palette, setPalette] = useState<PaletteId>(readPalette);

  function choose(id: PaletteId) {
    applyPalette(id);
    storePalette(id);
    setPalette(id);
  }

  return (
    <section className="palette-choice" aria-labelledby="palette-choice-title">
      <h2 id="palette-choice-title" className="lbl">
        Palette
      </h2>
      <div className="seg" role="group" aria-label="Palette">
        {PALETTES.map((p) => (
          <Control key={p.id} pressed={palette === p.id} title={p.note} aria-label={`${p.name}: ${p.note}`} onClick={() => choose(p.id)}>
            {p.name}
          </Control>
        ))}
      </div>
    </section>
  );
}
