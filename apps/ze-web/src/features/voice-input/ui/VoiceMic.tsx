import { Control } from "@/shared/ui";

/** The Ask bar's mic. `blocked` is the bar's own reason when it cannot be used. */
export function VoiceMic({ blocked }: { blocked: string | null }) {
  const label = blocked ?? "Speak to Ze (hold V)";
  return (
    <Control disabled aria-label={label} title={label}>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.25" aria-hidden="true">
        <rect x="5.5" y="1.5" width="5" height="8" rx="2.5" />
        <path d="M3 7.5a5 5 0 0 0 10 0M8 12.5v2" />
      </svg>
    </Control>
  );
}
