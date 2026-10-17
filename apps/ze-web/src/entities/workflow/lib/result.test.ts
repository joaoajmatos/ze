import type { WorkflowExecutionResponse } from "@myguyze/ze-client";
import { describe, expect, it } from "vitest";
import { lastResult } from "./result";

function exec(o: Partial<WorkflowExecutionResponse>): WorkflowExecutionResponse {
  return {
    id: "e1",
    workflow_id: "w1",
    status: "completed",
    step_results: [],
    error: null,
    failure_summary: null,
    summary: null,
    started_at: "2026-10-10T08:00:00Z",
    completed_at: "2026-10-10T08:01:00Z",
    created_at: "2026-10-10T08:00:00Z",
    ...o,
  };
}

describe("lastResult", () => {
  it("is never when there are no executions", () => {
    expect(lastResult([])).toEqual({ kind: "never" });
    expect(lastResult(undefined)).toEqual({ kind: "never" });
  });

  it("is ok for a completed latest run", () => {
    expect(lastResult([exec({})]).kind).toBe("ok");
  });

  it("is running for a running latest run", () => {
    expect(lastResult([exec({ status: "running", completed_at: null })]).kind).toBe("running");
  });

  it("carries failure_summary for a failed run, never error", () => {
    const r = lastResult([exec({ status: "failed", failure_summary: "Step 2 could not reach the calendar", error: "Traceback (most recent call last)" })]);
    expect(r).toEqual({ kind: "failed", text: "Step 2 could not reach the calendar" });
  });

  it("says Failed with no error text when the summary is null", () => {
    expect(lastResult([exec({ status: "failed", error: "boom" })])).toEqual({ kind: "failed", text: "Failed" });
  });

  it("uses the newest execution by created_at", () => {
    const old = exec({ id: "a", status: "failed", created_at: "2026-10-01T00:00:00Z" });
    const fresh = exec({ id: "b", created_at: "2026-10-09T00:00:00Z" });
    expect(lastResult([old, fresh]).kind).toBe("ok");
  });
});
