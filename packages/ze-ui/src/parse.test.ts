import { describe, it, expect } from "vitest";
import {
  parsePrimitive,
  parsePrimitiveTree,
  validatePrimitive,
  PrimitiveLegacyError,
  PrimitiveValidationError,
} from "./index";

describe("parsePrimitiveTree", () => {
  it("accepts a valid primitive tree", () => {
    const tree = parsePrimitiveTree([
      { type: "text", content: "Hello" },
    ], { version: "2.0" });
    expect(tree).toHaveLength(1);
    expect(tree[0]?.type).toBe("text");
  });

  it("turns an unknown node into a fallback and keeps the known one", () => {
    const tree = parsePrimitiveTree(
      [
        {
          type: "gauge",
          label: "Load",
          value: 0.4,
          nested: { skipped: true },
          rows: [{ type: "text", content: "inside" }],
        },
        { type: "text", content: "still here" },
      ],
      { version: "2.0" },
    );
    expect(tree[0]).toEqual({
      type: "__fallback",
      original: "gauge",
      fields: [
        ["label", "Load"],
        ["value", "0.4"],
      ],
      children: [{ type: "text", content: "inside" }],
    });
    expect(tree[1]).toMatchObject({ type: "text" });
  });

  it("keeps at most 12 scalar fields on a fallback", () => {
    const wide = Object.fromEntries(Array.from({ length: 20 }, (_, i) => [`f${i}`, i]));
    const [node] = parsePrimitiveTree([{ type: "future", ...wide }], { version: "2.0" });
    expect(node).toMatchObject({ type: "__fallback" });
    expect((node as { fields: unknown[] }).fields).toHaveLength(12);
  });

  it("falls back inside a known container", () => {
    const [col] = parsePrimitiveTree(
      [{ type: "col", children: [{ type: "future_card", title: "x" }] }],
      { version: "2.0" },
    );
    expect((col as { children: { type: string }[] }).children[0]?.type).toBe("__fallback");
  });

  it("parses a later minor version of the same major", () => {
    expect(() =>
      parsePrimitiveTree([{ type: "future" }, { type: "text", content: "x" }], { version: "2.3" }),
    ).not.toThrow();
  });

  it("names the node path and field when a known node is invalid", () => {
    try {
      parsePrimitiveTree([{ type: "col", children: [{ type: "text" }] }], { version: "2.0" });
      throw new Error("should have thrown");
    } catch (error) {
      expect(error).toBeInstanceOf(PrimitiveValidationError);
      const e = error as PrimitiveValidationError;
      expect(e.path).toBe("/0/children/0/content");
      expect(e.message).toContain("/0/children/0/content");
    }
  });

  it("points a bad action at the branch its kind selects", () => {
    try {
      parsePrimitiveTree(
        [{ type: "button", label: "Go", action: { kind: "navigate", route: "mind" } }],
        { version: "2.0" },
      );
      throw new Error("should have thrown");
    } catch (error) {
      expect((error as PrimitiveValidationError).path).toBe("/0/action/route");
    }
  });

  describe("legacy trees", () => {
    const stored = [
      {
        type: "col",
        children: [
          { type: "button", label: "Yes", style: "danger", action: "yes" },
          { type: "table", headers: ["a"], rows: [["1"]] },
        ],
      },
    ];

    it("parses with no version and with 1.4, turning string actions into legacy buttons", () => {
      for (const version of [undefined, null, "1.4"]) {
        const [col] = parsePrimitiveTree(stored, { version });
        const children = (col as { children: { type: string; label?: string }[] }).children;
        expect(children[0]).toEqual({ type: "__legacy_button", label: "Yes", style: "danger" });
        expect(children[1]?.type).toBe("table");
      }
    });

    it("rejects a string action under the current version", () => {
      expect(() => parsePrimitiveTree(stored, { version: "2.0" })).toThrow(PrimitiveValidationError);
    });

    it("throws PrimitiveLegacyError when a legacy tree still cannot parse", () => {
      expect(() => parsePrimitiveTree([{ type: "text" }], { version: null })).toThrow(
        PrimitiveLegacyError,
      );
    });
  });

  it("rejects missing required fields", () => {
    expect(() =>
      parsePrimitiveTree([{ type: "text" }], { version: "2.0" }),
    ).toThrow(PrimitiveValidationError);
  });

  it("rejects invalid nested child nodes", () => {
    expect(() =>
      parsePrimitiveTree([
        {
          type: "col",
          children: [{ type: "text" }],
        },
      ]),
    ).toThrow(PrimitiveValidationError);

    try {
      parsePrimitiveTree([
        {
          type: "col",
          children: [{ type: "text" }],
        },
      ]);
    } catch (error) {
      expect(error).toBeInstanceOf(PrimitiveValidationError);
      const validationError = error as PrimitiveValidationError;
      expect(validationError.issues.length).toBeGreaterThan(0);
    }
  });

  it("exposes a type guard for valid primitives", () => {
    expect(validatePrimitive({ type: "divider" })).toBe(true);
    expect(validatePrimitive({ type: "not-real" })).toBe(false);
  });

  it("parses a single primitive node", () => {
    const node = parsePrimitive({ type: "badge", label: "ok" });
    expect(node).toMatchObject({ type: "badge", label: "ok" });
  });
});
