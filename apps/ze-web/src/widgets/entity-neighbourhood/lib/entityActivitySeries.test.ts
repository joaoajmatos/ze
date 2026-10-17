import type { EntityDetailResponse } from "@myguyze/ze-client";
import { describe, expect, it } from "vitest";
import { entityActivitySeries } from "./entityActivitySeries";

describe("entityActivitySeries", () => {
  it("counts facts and episodes per day in date order", () => {
    const detail = {
      facts: [{ created_at: "2026-10-02T10:00:00Z" }, { created_at: "2026-10-02T11:00:00Z" }, { created_at: null }],
      episodes: [{ created_at: "2026-10-01T09:00:00Z" }, { created_at: "2026-10-02T09:00:00Z" }],
    } as unknown as EntityDetailResponse;
    expect(entityActivitySeries(detail)).toEqual([
      { x: "2026-10-01", y: 1, series: "episode" },
      { x: "2026-10-02", y: 2, series: "fact" },
      { x: "2026-10-02", y: 1, series: "episode" },
    ]);
  });

  it("is empty without activity", () => {
    expect(entityActivitySeries({ facts: [], episodes: [] } as unknown as EntityDetailResponse)).toEqual([]);
  });
});
