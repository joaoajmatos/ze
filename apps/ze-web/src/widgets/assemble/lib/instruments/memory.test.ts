import { describe, expect, it } from "vitest";
import { richTrace } from "./fixtures";
import { memoryPoints } from "./memory";

describe("memoryPoints", () => {
  const p = memoryPoints(richTrace().memory_chunks);

  it("plots x = score and y = extraction confidence, null on the floor", () => {
    expect(p.points[0]).toMatchObject({ x: 0.91, y: 0.9 });
    expect(p.points[2]).toMatchObject({ x: 0.6, y: null });
  });

  it("gives a glyph by source", () => {
    expect(p.points.map((x) => x.glyph)).toEqual(["fact", "fact", "episode", "profile", "fact"]);
  });

  it("ranks by score × confidence, a missing confidence counting as 0.5", () => {
    expect(p.ranked.map((x) => x.text)).toEqual(["Runs on Tuesdays", "Training for a 5k", "Met Ana in May", "Prefers mornings", "Owns a bike"]);
    expect(p.ranked[2].rank).toBeCloseTo(0.3);
  });

  it("is empty without chunks", () => {
    expect(memoryPoints(undefined).points).toEqual([]);
  });
});

describe("memoryPoints on a live trace", () => {
  it("plots a fact chunk from a partial frame by its extraction confidence", () => {
    const live = memoryPoints([{ text: "Runs on Tuesdays", score: 0.9, source: "fact", extraction_confidence: 0.8 }]);
    expect(live.points[0]).toMatchObject({ x: 0.9, y: 0.8, glyph: "fact" });
  });
});
