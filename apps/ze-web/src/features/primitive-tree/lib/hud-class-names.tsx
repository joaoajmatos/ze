import type { PrimitiveClassNames } from "@myguyze/ze-ui/react";
import { DotMatrix } from "@/shared/ui/hud";

/** The primitive atoms in the HUD system: the classes live in `shared/styles/ze.css` (`.pr-*`, `.ctl`). */
export const HUD_CLASS_NAMES: PrimitiveClassNames = {
  heading: "pr-heading",
  subheading: "pr-sub",
  body: "pr-body",
  label: "pr-label",
  caption: "pr-caption",
  code: "pr-code",
  muted: "pr-muted",
  badge: "pr-badge",
  card: "pr-card",
  progressTrack: "pr-track",
  progressFill: "pr-fill",
  table: "pr-table",
  steps: "pr-steps",
  connections: "pr-connections",
  button: "ctl",
  buttonPrimary: "primary",
  buttonDanger: "hot",
  claimCard: "pr-claim",
  claimTimeline: "pr-timeline",
  divider: "pr-divider",
};

export function renderHudHeadline(text: string) {
  return <DotMatrix text={text} size={3} title={text} />;
}
