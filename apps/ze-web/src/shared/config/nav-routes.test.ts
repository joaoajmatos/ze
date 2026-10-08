import { describe, expect, it } from "vitest";
import { getRoute, getRouteLabel } from "./nav-routes";

describe("getRouteLabel", () => {
  it.each([
    ["/", "Chat"],
    ["/goals", "Goals"],
    ["/goals/abc-123", "Goals"],
    ["/brain-memory", "Memory"],
    ["/data", "Data"],
    ["/settings", "Settings"],
  ])("%s -> %s", (pathname, label) => {
    expect(getRouteLabel(pathname)).toBe(label);
  });

  it("returns null for routes the manifest owns", () => {
    expect(getRouteLabel("/plugin/news")).toBeNull();
    expect(getRoute("/nowhere")).toBeNull();
  });
});
