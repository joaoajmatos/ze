import { Volume2, VolumeX } from "lucide-react";
import { Control } from "@/shared/ui";
import { useAmbience } from "../model/useAmbience";

/** The ambience switch in the Presence head. */
export function AmbienceToggle() {
  const { on, toggle } = useAmbience();
  const label = on ? "Ambience on" : "Ambience off";
  return (
    <Control pressed={on} aria-label={label} title={label} onClick={toggle}>
      {on ? <Volume2 size={16} aria-hidden="true" /> : <VolumeX size={16} aria-hidden="true" />}
    </Control>
  );
}
