import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { PrimitiveRendererContext } from "./context";
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

    it("drops the decision buttons once one is accepted and keeps Open", async () => {
      const onCardAction = vi.fn();
      render(
        <PrimitiveRenderer
          actions={{ onCardAction }}
          node={{
            type: "claim_card",
            title: "Reach B1",
            claim: { kind: "priority", subject: "goal", ref_id: "g1", slipped: false },
            actions: [
              { label: "Approve", intent: "approve_gate", ref_id: "g1" },
              { label: "Open", intent: "open", ref_id: "g1" },
            ],
          }}
        />,
      );
      fireEvent.click(screen.getByText("Approve"));
      expect(await screen.findByText("Sent.")).toBeInTheDocument();
      expect(screen.queryByText("Approve")).not.toBeInTheDocument();
      expect(screen.getByText("Open")).toBeInTheDocument();
      expect(onCardAction).toHaveBeenCalledTimes(1);
    });

    it("keeps the buttons and shows an error when the action is not accepted", async () => {
      const onCardAction = vi.fn(async () => false);
      render(
        <PrimitiveRenderer
          actions={{ onCardAction }}
          node={{
            type: "claim_card",
            title: "Reach B1",
            claim: { kind: "priority", subject: "goal", ref_id: "g1", slipped: false },
            actions: [{ label: "Approve", intent: "approve_gate", ref_id: "g1" }],
          }}
        />,
      );
      fireEvent.click(screen.getByText("Approve"));
      expect(await screen.findByText("Could not send. Try again.")).toBeInTheDocument();
      expect(screen.getByText("Approve")).toBeEnabled();
      expect(screen.queryByText("Sent.")).not.toBeInTheDocument();
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

describe("claim card chat about", () => {
  const card = {
    type: "claim_card" as const,
    title: "Reply to Ana",
    claim: { subject: "loop" as const, ref_id: "L1" },
  };

  it("shows no chip unless the host supplies onChatAbout", () => {
    render(<PrimitiveRenderer node={card} />);
    expect(screen.queryByRole("button", { name: /Chat about/ })).toBeNull();
  });

  it("shows the chip and calls back with the claim and the card element", () => {
    const onChatAbout = vi.fn();
    const { container } = render(
      <PrimitiveRendererContext.Provider value={{ onChatAbout }}>
        <PrimitiveRenderer node={card} />
      </PrimitiveRendererContext.Provider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Chat about Reply to Ana" }));
    expect(onChatAbout).toHaveBeenCalledWith({
      subject: "loop",
      ref_id: "L1",
      title: "Reply to Ana",
      element: container.querySelector(".claim-card"),
    });
  });
});

describe("PrimitiveRenderer classNames map (HUD restyle)", () => {
  const map = {
    heading: "x-heading",
    subheading: "x-sub",
    body: "x-body",
    label: "x-label",
    caption: "x-caption",
    muted: "x-muted",
    badge: "x-badge",
    card: "x-card",
    table: "x-table",
    steps: "x-steps",
    connections: "x-connections",
    button: "x-button",
    buttonPrimary: "x-primary",
    claimCard: "x-claim",
    claimTimeline: "x-timeline",
    divider: "x-divider",
  };
  const withMap = (node: Parameters<typeof PrimitiveRenderer>[0]["node"], extra = {}) =>
    render(<PrimitiveRendererContext.Provider value={{ classNames: map, ...extra }}><PrimitiveRenderer node={node} /></PrimitiveRendererContext.Provider>);

  it("maps the text variants and the muted colour", () => {
    withMap({ type: "col", children: [
      { type: "text", content: "big", style: "heading" },
      { type: "text", content: "lbl", style: "label" },
      { type: "text", content: "dim", style: "body", color: "muted" },
    ] });
    expect(screen.getByText("big")).toHaveClass("x-heading");
    expect(screen.getByText("lbl")).toHaveClass("x-label");
    expect(screen.getByText("dim")).toHaveClass("x-body", "x-muted");
  });

  it("maps badge, card-style col, table, steps, connections and button", () => {
    withMap({ type: "col", variant: "card", children: [
      { type: "badge", label: "b" },
      { type: "table", headers: ["h"], rows: [["c"]] },
      { type: "steps", steps: [{ label: "s", status: "done" }] },
      { type: "button", label: "go", action: { kind: "ask", text: "a" }, style: "primary" },
      { type: "divider" },
    ] });
    expect(screen.getByText("b")).toHaveClass("x-badge");
    expect(screen.getByText("go")).toHaveClass("x-button", "x-primary");
    expect(document.querySelector(".x-card")).not.toBeNull();
    expect(document.querySelector(".x-table")).not.toBeNull();
    expect(document.querySelector(".x-steps")).not.toBeNull();
    expect(document.querySelector(".x-divider")).not.toBeNull();
  });

  it("keeps the default classes when no map is given", () => {
    render(<PrimitiveRenderer node={{ type: "badge", label: "plain" }} />);
    expect(screen.getByText("plain").className).toContain("rounded-full");
  });

  it("renders a headline through the renderHeadline slot, else as plain text", () => {
    const { unmount } = withMap({ type: "headline", text: "3 slipping" }, { renderHeadline: (t: string) => <span data-testid="dm">{t}</span> });
    expect(screen.getByTestId("dm")).toHaveTextContent("3 slipping");
    unmount();
    withMap({ type: "headline", text: "3 slipping" });
    expect(screen.getByText("3 slipping")).toBeInTheDocument();
  });

  it("gives claim_card and claim_timeline their HUD classes", () => {
    withMap({ type: "claim_card", title: "Run 5k", claim: { subject: "goal", ref_id: "g1", kind: "goal" } } as never);
    expect(document.querySelector(".x-claim")).not.toBeNull();
    withMap({ type: "claim_timeline", title: "Ahead", entries: [{ title: "Pay rent", due_at: "2026-10-20T00:00:00Z" }] } as never);
    expect(document.querySelector(".x-timeline")).not.toBeNull();
  });
});
