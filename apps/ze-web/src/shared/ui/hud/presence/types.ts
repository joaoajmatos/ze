export type OrbState = "idle" | "listening" | "thinking" | "speaking" | "assembling" | "attention" | "acting" | "done" | "error";

export const ORB_STATES: readonly OrbState[] = ["idle", "listening", "thinking", "speaking", "assembling", "attention", "acting", "done", "error"];

export interface OrbColors {
  main: string;
  cream: string;
  coral: string;
  dim: string;
}

/** What a parent can ask the orb to do. */
export interface PresenceHandle {
  /** Look at an element (its centre) or a viewport point, as if it had just caught the orb's eye. */
  glance(target: Element | { x: number; y: number }): void;
}
