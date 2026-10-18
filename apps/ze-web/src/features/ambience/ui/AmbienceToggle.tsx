import { VolumeX } from "lucide-react";
import { Control } from "@/shared/ui";

/** The ambience switch in the Presence head. */
export function AmbienceToggle() {
  return (
    <Control pressed={false} aria-label="Ambience off" title="Ambience off">
      <VolumeX size={16} aria-hidden="true" />
    </Control>
  );
}
