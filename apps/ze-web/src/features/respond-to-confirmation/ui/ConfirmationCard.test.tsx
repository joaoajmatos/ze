import type { WsConfirmAction } from "@myguyze/ze-client";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ConfirmItem } from "../model/types";
import { ConfirmationCard } from "./ConfirmationCard";

const actions: WsConfirmAction[] = [
  { label: "Approve all", value: "approve", style: "primary" },
  { label: "Deny all", value: "deny", style: "secondary" },
];

function item(overrides: Partial<ConfirmItem> = {}): ConfirmItem {
  return {
    item_id: "c1",
    agent: "calendar",
    tool: "delete_event",
    effect_phrase: "delete a calendar event",
    summary: "Dentist — today 15:00",
    conflict: null,
    editable_field: null,
    proposed_text: null,
    ...overrides,
  };
}

describe("ConfirmationCard", () => {
  it("renders the title and one row per item with effect and summary", () => {
    render(
      <ConfirmationCard
        title="Ze needs your OK"
        items={[
          item(),
          item({
            item_id: "c2",
            tool: "send_email",
            effect_phrase: "send an email",
            summary: "To Ana — Notes",
          }),
        ]}
        actions={actions}
        onRespond={vi.fn()}
      />,
    );
    expect(screen.getByText("Ze needs your OK")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("delete a calendar event")).toBeInTheDocument();
    expect(screen.getByText("Dentist — today 15:00")).toBeInTheDocument();
    expect(screen.getByText("send an email")).toBeInTheDocument();
  });

  it("shows a warning badge only for items with a conflict", () => {
    render(
      <ConfirmationCard
        title="Ze needs your OK"
        items={[
          item({ conflict: "You said never to email Ana" }),
          item({ item_id: "c2", summary: "No conflict here" }),
        ]}
        actions={actions}
        onRespond={vi.fn()}
      />,
    );
    expect(screen.getAllByTestId("confirm-conflict")).toHaveLength(1);
    expect(screen.getByText("You said never to email Ana")).toBeInTheDocument();
  });

  it("shows where a held write came from", () => {
    render(
      <ConfirmationCard
        title="A workflow is waiting"
        items={[item()]}
        source={{ kind: "workflow", name: "Weekly summary" }}
        actions={actions}
        onRespond={vi.fn()}
      />,
    );
    expect(screen.getByText(/workflow/i, { selector: "[data-testid='confirm-source']" })).toHaveTextContent(
      "Weekly summary",
    );
  });

  it("prefills an editable field with the proposed text", () => {
    render(
      <ConfirmationCard
        title="Ze needs your OK"
        items={[
          item({
            item_id: "c2",
            tool: "send_email",
            effect_phrase: "send an email",
            editable_field: "body",
            proposed_text: "Hi Ana",
          }),
        ]}
        actions={actions}
        onRespond={vi.fn()}
      />,
    );
    expect(screen.getByRole("textbox")).toHaveValue("Hi Ana");
  });

  it("sends no edits when nothing was changed", () => {
    const onRespond = vi.fn();
    render(
      <ConfirmationCard
        title="Ze needs your OK"
        items={[item({ item_id: "c2", editable_field: "body", proposed_text: "Hi Ana" })]}
        actions={actions}
        onRespond={onRespond}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Approve all" }));
    expect(onRespond).toHaveBeenCalledWith("approve", {});
  });

  it("sends edits only for the items the user changed", () => {
    const onRespond = vi.fn();
    render(
      <ConfirmationCard
        title="Ze needs your OK"
        items={[
          item({ item_id: "c1", editable_field: "body", proposed_text: "Hi Ana" }),
          item({ item_id: "c2", editable_field: "body", proposed_text: "Hi Bo" }),
        ]}
        actions={actions}
        onRespond={onRespond}
      />,
    );
    const [first] = screen.getAllByRole("textbox");
    fireEvent.change(first, { target: { value: "Hello Ana" } });
    fireEvent.click(screen.getByRole("button", { name: "Approve all" }));
    expect(onRespond).toHaveBeenCalledWith("approve", { c1: "Hello Ana" });
  });

  it("sends deny without edits even when the user edited a field", () => {
    const onRespond = vi.fn();
    render(
      <ConfirmationCard
        title="Ze needs your OK"
        items={[item({ editable_field: "body", proposed_text: "Hi" })]}
        actions={actions}
        onRespond={onRespond}
      />,
    );
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "changed" } });
    fireEvent.click(screen.getByRole("button", { name: "Deny all" }));
    expect(onRespond).toHaveBeenCalledWith("deny", {});
  });

  it("disables both buttons once the answer is in flight", () => {
    render(
      <ConfirmationCard
        title="Ze needs your OK"
        items={[item()]}
        actions={actions}
        onRespond={vi.fn()}
        disabled
      />,
    );
    expect(screen.getByRole("button", { name: "Approve all" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Deny all" })).toBeDisabled();
  });

  it("renders a prompt-only card with no items and passes custom action values through", () => {
    const onRespond = vi.fn();
    render(
      <ConfirmationCard
        title="Milestone 2 is ready. Continue?"
        items={[]}
        actions={[
          { label: "Continue", value: "goal_gate:approve:abc", style: "primary" },
          { label: "Pause", value: "goal_gate:pause:abc", style: "secondary" },
        ]}
        onRespond={onRespond}
      />,
    );
    expect(screen.getByText("Milestone 2 is ready. Continue?")).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(onRespond).toHaveBeenCalledWith("goal_gate:pause:abc", {});
  });

  it("scrolls itself into view when highlighted", () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    render(
      <ConfirmationCard title="Ze needs your OK" items={[item()]} actions={actions} onRespond={vi.fn()} highlighted />,
    );
    expect(scrollIntoView).toHaveBeenCalled();
  });

  it("does not scroll when not highlighted", () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    render(<ConfirmationCard title="Ze needs your OK" items={[item()]} actions={actions} onRespond={vi.fn()} />);
    expect(scrollIntoView).not.toHaveBeenCalled();
  });
});
