import { describe, expect, it } from "vitest";
import { manifestFixture } from "@/test/fixtures/manifest";
import { modulesForSlot, presets } from "./select";

describe("modulesForSlot", () => {
  it("returns that slot's modules in manifest order", () => {
    const manifest = {
      ...manifestFixture,
      modules: [
        { ...manifestFixture.modules[0], id: "a.one" },
        manifestFixture.modules[1],
        { ...manifestFixture.modules[0], id: "b.two" },
      ],
    };
    expect(modulesForSlot(manifest, "mind.entity").map((m) => m.id)).toEqual(["a.one", "b.two"]);
    expect(modulesForSlot(manifest, "doing.run").map((m) => m.slot)).toEqual(["doing.run"]);
  });

  it("gives [] for an empty or absent manifest", () => {
    expect(modulesForSlot(undefined, "mind.entity")).toEqual([]);
    expect(modulesForSlot(null, "mind.entity")).toEqual([]);
    expect(modulesForSlot({ modules: [], presets: [], settings_sections: [] }, "doing.run")).toEqual([]);
  });
});

describe("presets", () => {
  it("returns the manifest's presets", () => {
    expect(presets(manifestFixture).map((p) => p.prompt)).toEqual(["Show the fixture"]);
    expect(presets(undefined)).toEqual([]);
  });
});
