import { describe, expect, it } from "vitest";
import { formatCost, formatTotal } from "./money";

describe("money", () => {
  it("prints totals with two decimals", () => {
    expect(formatTotal(0)).toBe("$0.00");
    expect(formatTotal(12.3456)).toBe("$12.35");
    expect(formatTotal(0.004)).toBe("$0.00");
  });

  it("prints a run or baseline cost under $1 with four decimals", () => {
    expect(formatCost(0.0123456)).toBe("$0.0123");
    expect(formatCost(0.9999)).toBe("$0.9999");
  });

  it("prints a run or baseline cost of $1 or more with two decimals", () => {
    expect(formatCost(1)).toBe("$1.00");
    expect(formatCost(3.456)).toBe("$3.46");
  });
});
