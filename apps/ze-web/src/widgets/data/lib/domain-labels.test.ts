import { describe, expect, it } from "vitest";
import { domainLabel } from "./domain-labels";

describe("domainLabel", () => {
  it.each([
    ["memory.facts", "Facts"],
    ["memory.episodes", "Episodes"],
    ["goals.goals", "Goals"],
    ["contacts.persons", "People"],
    ["messages.store", "Messages"],
    ["telemetry.costs", "Spend history"],
    ["graph.checkpoints", "Conversation state"],
  ])("%s is %s", (id, label) => {
    expect(domainLabel(id)).toBe(label);
  });

  it("humanises an unknown id without a raw table name", () => {
    expect(domainLabel("acme.widget_orders")).toBe("Widget orders");
    expect(domainLabel("solo")).toBe("Solo");
    expect(domainLabel("acme.widget_orders")).not.toMatch(/[._]/);
  });
});
