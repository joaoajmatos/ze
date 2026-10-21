import type { ModuleSlot, UiContribution, UiManifest } from "./types";

/** The modules filling `slot`, in the manifest's priority order. */
export function modulesForSlot(manifest: UiManifest | null | undefined, slot: ModuleSlot): UiContribution[] {
  return (manifest?.modules ?? []).filter((m) => m.slot === slot);
}

/** The Ask preset chips plugins contribute, in priority order. */
export function presets(manifest: UiManifest | null | undefined): UiContribution[] {
  return manifest?.presets ?? [];
}

/** The key a subject adds to a module's query key. */
export function subjectKey(subject: { kind: string; id?: string; parent_id?: string }): string {
  return [subject.kind, subject.id ?? "", subject.parent_id ?? ""].join(":");
}
