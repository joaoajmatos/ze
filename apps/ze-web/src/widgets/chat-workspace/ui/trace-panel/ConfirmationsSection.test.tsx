import type { WriteConfirmationOutcomeResponse } from "@myguyze/ze-client";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConfirmationsSection } from "./ConfirmationsSection";

function outcome(
  overrides: Partial<WriteConfirmationOutcomeResponse> = {},
): WriteConfirmationOutcomeResponse {
  return {
    request_id: "req-1",
    round: 1,
    item_id: "c1",
    agent: "calendar",
    tool: "delete_event",
    effect: "deleted a calendar event",
    summary: "Dentist — today 15:00",
    outcome: "approved",
    ...overrides,
  };
}

describe("ConfirmationsSection", () => {
  it("renders nothing when there are no confirmations", () => {
    const { container } = render(<ConfirmationsSection outcomes={[]} />);
    expect(container).toBeEmptyDOMElement();
    const { container: undef } = render(<ConfirmationsSection outcomes={undefined} />);
    expect(undef).toBeEmptyDOMElement();
  });

  it("lists the tool, summary and an outcome badge", () => {
    render(<ConfirmationsSection outcomes={[outcome()]} />);
    expect(screen.getByText("Confirmations")).toBeInTheDocument();
    expect(screen.getByText("delete_event")).toBeInTheDocument();
    expect(screen.getByText("Dentist — today 15:00")).toBeInTheDocument();
    expect(screen.getByText("Approved")).toBeInTheDocument();
  });

  it.each([
    ["approved", "Approved"],
    ["edited", "Edited"],
    ["denied", "Denied"],
    ["timed_out", "Timed out"],
    ["superseded", "Superseded"],
    ["refused", "Refused"],
    ["pre_approved", "Pre-approved"],
  ])("labels the %s outcome", (value, label) => {
    render(
      <ConfirmationsSection
        outcomes={[outcome({ outcome: value as WriteConfirmationOutcomeResponse["outcome"] })]}
      />,
    );
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("groups items by round", () => {
    render(
      <ConfirmationsSection
        outcomes={[
          outcome({ round: 1, item_id: "a", tool: "create_event", outcome: "approved" }),
          outcome({ round: 2, item_id: "b", tool: "send_email", outcome: "denied" }),
          outcome({ round: 1, item_id: "c", tool: "update_event", outcome: "edited" }),
        ]}
      />,
    );
    const groups = screen.getAllByRole("group");
    expect(groups).toHaveLength(2);
    expect(within(groups[0]).getByText("Round 1")).toBeInTheDocument();
    expect(within(groups[0]).getByText("create_event")).toBeInTheDocument();
    expect(within(groups[0]).getByText("update_event")).toBeInTheDocument();
    expect(within(groups[1]).getByText("Round 2")).toBeInTheDocument();
    expect(within(groups[1]).getByText("send_email")).toBeInTheDocument();
  });

  it("falls back to the agent when an item has no tool", () => {
    render(
      <ConfirmationsSection
        outcomes={[outcome({ tool: null, agent: "budget", summary: "$4.10 of $4.00" })]}
      />,
    );
    expect(screen.getByText("budget")).toBeInTheDocument();
  });
});
