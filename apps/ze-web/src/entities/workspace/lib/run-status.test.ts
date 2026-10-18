import type { WorkspaceRunResponse } from "@myguyze/ze-client";
import { describe, expect, it } from "vitest";
import { isAlarm, originWord, statusWord } from "./run-status";

const run = (o: Partial<WorkspaceRunResponse>) => ({ status: "succeeded", origin: "conversation", ...o }) as WorkspaceRunResponse;

describe("run words", () => {
  it("has plain words for every status", () => {
    for (const s of ["succeeded", "failed", "timed_out", "cancelled", "refused", "in_progress"] as const) {
      expect(statusWord(s)).not.toMatch(/_/);
    }
    expect(statusWord("timed_out")).toBe("Timed out");
    expect(statusWord("in_progress")).toBe("Running");
  });
  it("humanises an unknown origin", () => {
    expect(originWord("unattended")).toBe("On its own");
    expect(originWord("user")).toBe("You");
    expect(originWord("some_new_origin")).toBe("Some new origin");
  });
});

describe("isAlarm", () => {
  it("is true only for unattended failed or timed out", () => {
    expect(isAlarm(run({ origin: "unattended", status: "failed" }))).toBe(true);
    expect(isAlarm(run({ origin: "unattended", status: "timed_out" }))).toBe(true);
    expect(isAlarm(run({ origin: "unattended", status: "cancelled" }))).toBe(false);
    expect(isAlarm(run({ origin: "unattended", status: "refused" }))).toBe(false);
    expect(isAlarm(run({ origin: "conversation", status: "failed" }))).toBe(false);
    expect(isAlarm(run({ origin: "user", status: "timed_out" }))).toBe(false);
  });
});
