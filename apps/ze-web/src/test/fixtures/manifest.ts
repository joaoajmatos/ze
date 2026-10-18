import type { UiManifest } from "@/entities/ui-manifest";

/** One module per slot, one preset and one settings section, as the fixture plugin sends them. */
export const manifestFixture: UiManifest = {
  modules: [
    { id: "fixture.entity", plugin: "fixture", kind: "module", label: "Fixture facet", icon: "box", slot: "mind.entity", priority: 100 },
    { id: "fixture.run", plugin: "fixture", kind: "module", label: "Fixture run", icon: "box", slot: "doing.run", priority: 100 },
    { id: "fixture.card", plugin: "fixture", kind: "module", label: "Fixture card", icon: "box", slot: "governance.connections", priority: 100 },
  ],
  presets: [
    { id: "fixture.preset", plugin: "fixture", kind: "preset", label: "Fixture preset", icon: "box", prompt: "Show the fixture", priority: 100 },
  ],
  settings_sections: [
    { id: "fixture.settings", plugin: "fixture", kind: "settings_section", label: "Fixture", icon: "box", settings_operation_id: "getNewsSettings", priority: 100 },
  ],
};
