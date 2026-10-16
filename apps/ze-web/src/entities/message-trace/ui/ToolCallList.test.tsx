import type { ToolCallTraceResponse } from "@myguyze/ze-client";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ToolCallList } from "./ToolCallList";

function call(overrides: Partial<ToolCallTraceResponse> = {}): ToolCallTraceResponse {
  return { name: "send_email", duration_ms: 12, success: true, ...overrides } as ToolCallTraceResponse;
}

describe("ToolCallList gate label", () => {
  it.each([
    ["approved", "Approved"],
    ["pre_approved", "Pre-approved"],
    ["denied", "Denied"],
    ["refused", "Refused"],
    ["refused_over_cap", "Refused"],
    ["expired", "Timed out"],
    ["duplicate", "Not repeated"],
  ] as const)("shows %s as %s", (gate, label) => {
    render(<ToolCallList toolCalls={[call({ gate })]} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("shows nothing for an ungated call", () => {
    render(<ToolCallList toolCalls={[call({ gate: "none" })]} />);
    expect(screen.queryByTestId("tool-gate")).toBeNull();
  });

  it("shows nothing when the trace has no gate", () => {
    render(<ToolCallList toolCalls={[call()]} />);
    expect(screen.queryByTestId("tool-gate")).toBeNull();
  });
});
