import { describe, expect, it } from "vitest";
import { parseFocus } from "./focus";

describe("parseFocus", () => {
  it.each([
    ["loop:abc", { kind: "loop", id: "abc" }],
    ["held_write:r-1", { kind: "held_write", id: "r-1" }],
    ["reminder:r", { kind: "reminder", id: "r" }],
    ["hypothesis:h", { kind: "hypothesis", id: "h" }],
    ["goal:g", { kind: "goal", id: "g" }],
    ["loop:a:b", { kind: "loop", id: "a:b" }],
    ["loop:a%20b", { kind: "loop", id: "a b" }],
  ])("parses %s", (raw, want) => {
    expect(parseFocus(raw)).toEqual(want);
  });

  it.each([[null], [""], ["loop"], ["loop:"], ["martian:1"], [":1"]])("ignores %j", (raw) => {
    expect(parseFocus(raw)).toBeNull();
  });
});
