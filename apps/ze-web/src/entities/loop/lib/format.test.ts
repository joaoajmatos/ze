import { describe, expect, it } from "vitest";
import { promotedLine, sourceLabel } from "./format";

describe("sourceLabel", () => {
  it("maps the known inflows to readable labels", () => {
    expect(sourceLabel("conversation")).toBe("chat");
    expect(sourceLabel("email")).toBe("email");
    expect(sourceLabel("calendar")).toBe("calendar");
    expect(sourceLabel("ingestion")).toBe("a document");
  });

  it("falls back to the raw inflow for an unknown source", () => {
    expect(sourceLabel("prospecting")).toBe("prospecting");
  });
});

describe("promotedLine", () => {
  it("returns the promotion line with labels for a promoted loop", () => {
    expect(
      promotedLine({ promoted: true, source_inflows: ["conversation", "email"] })
    ).toBe("Promoted · seen in: chat, email");
  });

  it("returns null for a loop that was not promoted", () => {
    expect(
      promotedLine({ promoted: false, source_inflows: ["conversation", "email"] })
    ).toBeNull();
  });

  it("degrades to 'Promoted' when a promoted loop lists no inflows", () => {
    expect(promotedLine({ promoted: true, source_inflows: [] })).toBe("Promoted");
  });
});
