import { describe, expect, it } from "vitest";
import { plainPreview } from "./plainPreview";

describe("plainPreview", () => {
  it("drops emphasis, including a mark the preview cut off", () => {
    expect(plainPreview("You have **two** loops")).toBe("You have two loops");
    expect(plainPreview("**renew")).toBe("renew");
  });
  it("keeps link text, drops list and heading marks and flattens lines", () => {
    expect(plainPreview("# Plan\n- see [the doc](http://x)\n- done")).toBe("Plan see the doc done");
  });
});
