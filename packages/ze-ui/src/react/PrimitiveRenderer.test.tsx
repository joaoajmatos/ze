import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { fixture } from "../test/fixtures";
import { parsePrimitiveTree } from "../parse";
import { PrimitiveRendererContext } from "./context";
import { PrimitiveRenderer, PrimitiveTreeRenderer } from "./PrimitiveRenderer";

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

describe("fallback and legacy nodes", () => {
  it("renders an unknown node as a two-column table with its known children inside", () => {
    const [node] = parsePrimitiveTree(
      [
        {
          type: "gauge",
          label: "Load",
          value: 0.4,
          children: [{ type: "text", content: "inside" }],
        },
      ],
      { version: "2.0" },
    );
    render(<PrimitiveRenderer node={node!} />);
    expect(screen.getByText("Unsupported view: gauge")).toBeInTheDocument();
    expect(screen.getByText("label")).toBeInTheDocument();
    expect(screen.getByText("Load")).toBeInTheDocument();
    expect(screen.getByText("0.4")).toBeInTheDocument();
    expect(screen.getByText("inside")).toBeInTheDocument();
  });

  it("renders a stored pre-191a tree: its table, and its string button disabled with a title", () => {
    const tree = parsePrimitiveTree(
      [
        { type: "button", label: "Yes", action: "yes" },
        { type: "table", headers: ["a", "b"], rows: [["1", "2"]] },
      ],
      { version: null },
    );
    const onAction = vi.fn();
    render(<PrimitiveTreeRenderer nodes={tree} actions={{ onAction }} />);
    const button = screen.getByRole("button", { name: "Yes" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("title", "This older button no longer works.");
    fireEvent.click(button);
    expect(onAction).not.toHaveBeenCalled();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("renders no known node type as nothing", () => {
    const fixtures = [
      { type: "divider" },
      { type: "spacer" },
      { type: "col", children: [] },
      { type: "row", children: [] },
      { type: "headline", text: "H" },
      { type: "sparkline", label: "S", points: [] },
      { type: "claim_list", items: [] },
      { type: "entity_facet", title: "E", facts: [] },
      { type: "card", title: "C", children: [] },
    ] as const;
    for (const node of fixtures) {
      const { container, unmount } = render(<PrimitiveRenderer node={node as never} />);
      expect(container.firstChild).not.toBeNull();
      unmount();
    }
  });
});

const posture = (kind: string, extra: object = {}) => ({
  kind,
  subject: "fact",
  ref_id: "f-1",
  source: "you said so",
  confidence: 0.8,
  ...extra,
});

function fixtureTree(name: string) {
  return parsePrimitiveTree(fixture(name), { version: "2.0" });
}

describe("slot primitives", () => {
  it("entity_facet shows each fact with its posture tone and source", () => {
    render(
      <PrimitiveRenderer
        node={{
          type: "entity_facet",
          title: "Maria",
          facts: [
            { text: "Works in Lisbon", claim: posture("fact") as never, source: "email" },
            { text: "May leave", claim: posture("suspicion", { confidence: 0.3 }) as never },
          ],
        }}
      />,
    );
    expect(screen.getByText("Maria")).toBeInTheDocument();
    const fact = screen.getByText("Works in Lisbon").closest("li")!;
    expect(fact).toHaveTextContent("fact");
    expect(fact).toHaveTextContent("email");
    const suspicion = screen.getByText("May leave").closest("li")!;
    expect(suspicion).toHaveAttribute("data-kind", "suspicion");
    expect(suspicion).toHaveTextContent("30%");
  });

  it("entity_facet runs its 'more' action", () => {
    const onAction = vi.fn();
    render(
      <PrimitiveRenderer
        actions={{ onAction }}
        node={{
          type: "entity_facet",
          title: "Maria",
          facts: [],
          more: { kind: "navigate", route: "/mind/ent-42" },
        }}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /more/i }));
    expect(onAction).toHaveBeenCalledWith({ kind: "navigate", route: "/mind/ent-42" });
  });

  it("stat_row shows value and change with a direction word, not color alone", () => {
    render(
      <PrimitiveRenderer
        node={{
          type: "stat_row",
          items: [
            { label: "Spent", value: "€42", delta: "+€8", direction: "up" },
            { label: "Runs", value: "12", delta: "-3", direction: "down" },
            { label: "Held", value: "0", direction: "flat" },
          ],
        }}
      />,
    );
    expect(screen.getByText("€42")).toBeInTheDocument();
    expect(screen.getByText("+€8")).toBeInTheDocument();
    expect(screen.getByText(/up/i, { selector: ".sr-only, [data-direction-label]" })).toBeInTheDocument();
    expect(screen.getByText(/down/i, { selector: ".sr-only, [data-direction-label]" })).toBeInTheDocument();
  });

  it("claim_list shows each item's posture and runs its action", () => {
    const onAction = vi.fn();
    render(
      <PrimitiveRenderer
        actions={{ onAction }}
        node={{
          type: "claim_list",
          title: "Open",
          items: [
            {
              text: "Call the dentist",
              claim: posture("priority", { subject: "loop" }) as never,
              action: { kind: "ask", text: "Tell me more" },
            },
            { text: "Renew passport", claim: posture("suspicion", { subject: "loop" }) as never },
          ],
        }}
      />,
    );
    expect(screen.getByText("Call the dentist").closest("li")).toHaveAttribute("data-kind", "priority");
    expect(screen.getByText("Renew passport").closest("li")).toHaveTextContent("suspicion");
    fireEvent.click(screen.getByRole("button", { name: /Call the dentist/ }));
    expect(onAction).toHaveBeenCalledWith({ kind: "ask", text: "Tell me more" });
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("sparkline draws at most 60 points and shows its label", () => {
    const points = Array.from({ length: 100 }, (_, i) => i);
    const { container } = render(
      <PrimitiveRenderer node={{ type: "sparkline", label: "Daily spend", points, value: "€6" }} />,
    );
    expect(screen.getByText("Daily spend")).toBeInTheDocument();
    expect(screen.getByText("€6")).toBeInTheDocument();
    const path = container.querySelector("svg polyline, svg path")!;
    const raw = path.getAttribute("points") ?? path.getAttribute("d") ?? "";
    expect(raw.trim().split(/[\sLM]+/).filter(Boolean)).toHaveLength(60);
  });

  it("sparkline with a single point or none still renders its label", () => {
    render(<PrimitiveRenderer node={{ type: "sparkline", label: "One", points: [2] }} />);
    expect(screen.getByText("One")).toBeInTheDocument();
    render(<PrimitiveRenderer node={{ type: "sparkline", label: "None", points: [] }} />);
    expect(screen.getByText("None")).toBeInTheDocument();
  });

  it("card renders children and its action buttons", () => {
    const onAction = vi.fn();
    const [card] = fixtureTree("card");
    render(<PrimitiveRenderer node={card!} actions={{ onAction }} />);
    expect(screen.getByText("Goal: run 5k")).toBeInTheDocument();
    expect(screen.getByText("On track")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(onAction).toHaveBeenCalledWith({ kind: "navigate", route: "/doing" });
  });

  it("a keyed table's row action fills {key} from the row", () => {
    const onAction = vi.fn();
    const [table] = fixtureTree("table-keyed");
    render(<PrimitiveRenderer node={table!} actions={{ onAction }} />);
    const buttons = screen.getAllByRole("button", { name: "Mark read" });
    expect(buttons).toHaveLength(2);
    fireEvent.click(buttons[1]!);
    expect(onAction).toHaveBeenCalledWith({
      kind: "tool",
      owner: "news",
      tool: "mark_source_read",
      args: { source_id: "s-2" },
    });
  });

  it("every button calls onAction with its typed action", () => {
    const onAction = vi.fn();
    const [row] = fixtureTree("button");
    render(<PrimitiveRenderer node={row!} actions={{ onAction }} />);
    const buttons = screen.getAllByRole("button");
    buttons.forEach((b) => fireEvent.click(b));
    expect(onAction.mock.calls.map(([a]) => a.kind)).toEqual(["ask", "navigate", "compose", "tool"]);
  });

  it("gives every interactive element a 44 px target", () => {
    const nodes = [
      ...fixtureTree("button"),
      ...fixtureTree("card"),
      ...fixtureTree("claim_list"),
      ...fixtureTree("entity_facet"),
      ...fixtureTree("table-keyed"),
    ];
    const { container } = render(
      <PrimitiveTreeRenderer nodes={nodes} actions={{ onAction: vi.fn() }} />,
    );
    const interactive = container.querySelectorAll("button, a, input, select");
    expect(interactive.length).toBeGreaterThan(5);
    interactive.forEach((el) => expect(el).toHaveClass("min-h-11"));
  });
});
