import { describe, expect, it } from "vitest";
import schema from "./generated/schema.json";
import { parsePrimitiveTree, PrimitiveValidationError } from "./index";
import { fixture, fixtureExpect, fixtureNames } from "./test/fixtures";

function types(node: unknown, into: Set<string>): void {
  if (Array.isArray(node)) {
    node.forEach((n) => types(n, into));
  } else if (node && typeof node === "object") {
    const record = node as Record<string, unknown>;
    if (typeof record.type === "string") into.add(record.type);
    Object.values(record).forEach((v) => types(v, into));
  }
}

describe("shared fixtures", () => {
  for (const name of fixtureNames) {
    it(`${name} matches its client expectation`, () => {
      const tree = fixture(name);
      const want = fixtureExpect(name);
      const version = "version" in want ? want.version : "2.0";
      if (typeof want.client === "object") {
        try {
          parsePrimitiveTree(tree, { version });
        } catch (error) {
          expect(error).toBeInstanceOf(PrimitiveValidationError);
          expect((error as PrimitiveValidationError).path).toBe(want.client.invalid_at);
          return;
        }
        throw new Error(`${name} parsed but should be invalid at ${want.client.invalid_at}`);
      }
      expect(() => parsePrimitiveTree(tree, { version })).not.toThrow();
    });
  }

  it("has a valid fixture for every primitive type", () => {
    const seen = new Set<string>();
    for (const name of fixtureNames) {
      if (fixtureExpect(name).client === "valid") types(fixture(name), seen);
    }
    const all = Object.keys(schema.discriminator.mapping);
    expect(all.filter((t) => !seen.has(t))).toEqual([]);
  });
});
