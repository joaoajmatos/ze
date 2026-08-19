import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
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
});
