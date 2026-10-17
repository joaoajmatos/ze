import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { PrimitiveRenderer } from "./PrimitiveRenderer";

describe("PrimitiveRenderer", () => {
  it("renders a text primitive", () => {
    render(<PrimitiveRenderer node={{ type: "text", content: "Hello world" }} />);
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  it("renders a table primitive", () => {
    render(
      <PrimitiveRenderer
        node={{
          type: "table",
          headers: ["Agent", "Cost"],
          rows: [["research", "$0.50"]],
          title: "Spend",
        }}
      />,
    );
    expect(screen.getByText("Spend")).toBeInTheDocument();
    expect(screen.getByText("research")).toBeInTheDocument();
  });

  it("renders a col with nested text children", () => {
    render(
      <PrimitiveRenderer
        node={{
          type: "col",
          children: [
            { type: "text", content: "$1.23", style: "heading" },
            { type: "text", content: "Total cost", style: "label" },
          ],
        }}
      />,
    );
    expect(screen.getByText("$1.23")).toBeInTheDocument();
    expect(screen.getByText("Total cost")).toBeInTheDocument();
  });

  it("renders a badge", () => {
    render(<PrimitiveRenderer node={{ type: "badge", label: "done", color: "success" }} />);
    expect(screen.getByText("done")).toBeInTheDocument();
  });

  it("renders a row with badges", () => {
    render(
      <PrimitiveRenderer
        node={{
          type: "row",
          children: [
            { type: "badge", label: "A" },
            { type: "badge", label: "B" },
          ],
        }}
      />,
    );
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("B")).toBeInTheDocument();
  });

  it("renders a connections primitive", () => {
    render(
      <PrimitiveRenderer
        node={{
          type: "connections",
          title: "Linked insights",
          connections: [
            {
              summary: "You work late before deadlines",
              narrative: "Seen in 3 episodes",
              relation: "pattern",
              confidence: 0.8,
            },
          ],
        }}
      />,
    );
    expect(screen.getByText("Linked insights")).toBeInTheDocument();
    expect(screen.getByText("You work late before deadlines")).toBeInTheDocument();
  });

  it("renders a steps primitive with title, labels, and notes", () => {
    render(
      <PrimitiveRenderer
        node={{
          type: "steps",
          title: "Reach B1 Portuguese",
          steps: [
            { label: "Complete A2 assessment", status: "done" },
            { label: "Weekly conversation practice", status: "active", note: "2x per week" },
            { label: "B1 mock exam", status: "pending" },
          ],
        }}
      />,
    );
    expect(screen.getByText("Reach B1 Portuguese")).toBeInTheDocument();
    expect(screen.getByText("Complete A2 assessment")).toBeInTheDocument();
    expect(screen.getByText("2x per week")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
  });

  it("renders a line chart without throwing", () => {
    render(
      <PrimitiveRenderer
        node={{
          type: "chart",
          chart_type: "line",
          data: [
            { x: "2026-01-01", y: 1 },
            { x: "2026-01-02", y: 2 },
          ],
          title: "Trend",
        }}
      />,
    );
    expect(screen.getByText("Trend")).toBeInTheDocument();
  });

  it("renders a bar chart without throwing", () => {
    render(
      <PrimitiveRenderer
        node={{
          type: "chart",
          chart_type: "bar",
          data: [
            { x: "A", y: 1 },
            { x: "B", y: 2 },
          ],
        }}
      />,
    );
  });

  it("renders an area chart without throwing", () => {
    render(
      <PrimitiveRenderer
        node={{
          type: "chart",
          chart_type: "area",
          data: [{ x: "2026-01-01", y: 1 }],
        }}
      />,
    );
  });

  it("renders a pie chart without throwing", () => {
    render(
      <PrimitiveRenderer
        node={{
          type: "chart",
          chart_type: "pie",
          data: [
            { x: "A", y: 1 },
            { x: "B", y: 2 },
          ],
        }}
      />,
    );
  });

  it("renders an empty-state for a chart with no data", () => {
    render(<PrimitiveRenderer node={{ type: "chart", chart_type: "line", data: [] }} />);
    expect(screen.getByText("No data")).toBeInTheDocument();
  });

  it("degrades gracefully for an unrecognized chart_type", () => {
    const { container } = render(
      // @ts-expect-error — simulating a newer backend's unsupported chart_type
      <PrimitiveRenderer node={{ type: "chart", chart_type: "scatter", data: [{ x: "A", y: 1 }] }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders inline markdown in text primitives", () => {
    render(
      <PrimitiveRenderer node={{ type: "text", content: "Focus on **conversation** next" }} />,
    );
    const strong = screen.getByText("conversation");
    expect(strong.tagName).toBe("STRONG");
    expect(screen.queryByText(/\*\*/)).not.toBeInTheDocument();
  });

  describe("claim primitives", () => {
    const claim = { kind: "suspicion", subject: "loop", ref_id: "l1", slipped: false } as const;

    it("renders a headline as its text", () => {
      render(<PrimitiveRenderer node={{ type: "headline", text: "2 SLIPPING" }} />);
      expect(screen.getByText("2 SLIPPING")).toBeInTheDocument();
    });

    it("renders a claim card with lines, readouts and one button per action", () => {
      const onCardAction = vi.fn();
      render(
        <PrimitiveRenderer
          actions={{ onCardAction }}
          node={{
            type: "claim_card",
            title: "Call the bank",
            claim,
            lines: ["Seen in email"],
            readouts: [{ label: "confidence", value: "0.55" }],
            actions: [
              { label: "Yes, track it", intent: "confirm_loop", ref_id: "l1" },
              { label: "Drop", intent: "drop_loop", ref_id: "l1" },
            ],
          }}
        />,
      );
      expect(screen.getByText("Call the bank")).toBeInTheDocument();
      expect(screen.getByText("Seen in email")).toBeInTheDocument();
      expect(screen.getByText("confidence")).toBeInTheDocument();
      expect(screen.getByText("0.55")).toBeInTheDocument();
      expect(screen.getAllByRole("button")).toHaveLength(2);
      fireEvent.click(screen.getByText("Yes, track it"));
      expect(onCardAction).toHaveBeenCalledWith({
        intent: "confirm_loop",
        ref_id: "l1",
        subject: "loop",
      });
    });

    it("shows the claim's posture on a card", () => {
      render(
        <PrimitiveRenderer
          node={{
            type: "claim_card",
            title: "Reply to Ana",
            claim: { kind: "priority", subject: "loop", ref_id: "l1", state: "drifting", confidence: 0.62, slipped: true },
          }}
        />,
      );
      expect(screen.getByText("priority · drifting · 62% · slipped")).toBeInTheDocument();
    });

    it("names the subject when a card's claim has no kind", () => {
      render(
        <PrimitiveRenderer
          node={{ type: "claim_card", title: "Send", claim: { kind: undefined, subject: "held_write", ref_id: "h1", state: "open", slipped: false } }}
        />,
      );
      expect(screen.getByText("held write · open")).toBeInTheDocument();
    });

    it("renders claim timeline entries in order", () => {
      render(
        <PrimitiveRenderer
          node={{
            type: "claim_timeline",
            title: "Past 7 days to next 7",
            entries: [
              { title: "First", claim, due_at: "2026-10-01T00:00:00Z" },
              { title: "Second", claim },
            ],
          }}
        />,
      );
      const items = screen.getAllByRole("listitem").map((li) => li.textContent ?? "");
      expect(items[0]).toContain("First");
      expect(items[1]).toContain("Second");
    });

    it("renders a primitive that carries a claim unchanged", () => {
      render(<PrimitiveRenderer node={{ type: "text", content: "Plain", claim }} />);
      expect(screen.getByText("Plain")).toBeInTheDocument();
    });
  });
});
