import { describe, expect, it } from "vitest";
import { automationNavRoutes, getRoute, getRouteLabel, navRoutes } from "./nav-routes";

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

  it("labels the loops route", () => {
    expect(getRouteLabel("/loops")).toBe("Open loops");
  });
});

describe("navRoutes", () => {
  it("places the loops route directly after priority", () => {
    const priorityIndex = navRoutes.findIndex((r) => r.path === "priority");
    expect(navRoutes[priorityIndex + 1]).toMatchObject({
      path: "loops",
      label: "Open loops",
      showInMobileNav: false,
    });
  });

  it("lists the loops route in the automation group in nav order", () => {
    expect(automationNavRoutes.map((r) => r.path)).toEqual([
      "goals",
      "priority",
      "loops",
      "workflows",
      "skills",
    ]);
  });
});
