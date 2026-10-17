import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Concern } from "@/shared/lib";
import { concern, NOW } from "../lib/fixtures";
import { useReorder } from "../lib/useReorder";
import { FieldChart } from "./FieldChart";

const now = NOW;
const day = (n: number) => new Date(now.getTime() + n * 86_400_000);

function Harness({ concerns, selected = null, onSelect = () => {} }: { concerns: Concern[]; selected?: string | null; onSelect?: (k: string | null) => void }) {
  const reorder = useReorder(concerns, () => {});
  return <FieldChart concerns={concerns} now={now} selected={selected} onSelect={onSelect} reorder={reorder} />;
}

describe("FieldChart", () => {
  const concerns = [
    concern("told", { provenance: "user_declared", due: day(2), confidence: 0.9 }),
    concern("inferred", { claimKind: "inference", due: day(3), confidence: 0.5 }),
    concern("suspected", { state: "suspected", due: day(4), confidence: 0.3 }),
    concern("goal", { kind: "goal", key: "goal:goal", state: "active", slipped: true, confidence: null, due: day(5), title: "Ship the thing" }),
    concern("ana", { title: "Reply to Ana", state: "drifting", slipped: true, due: day(-3), confidence: 0.62, confidencePrior: 0.8 }),
  ];

  it("renders every mark as a focusable button with an accessible name", () => {
    render(<Harness concerns={concerns} />);
    const mark = screen.getByRole("button", { name: "Reply to Ana, drifting, slipped 3 days ago, 62% sure" });
    expect(mark.getAttribute("tabindex")).toBe("0");
    expect(screen.getAllByRole("button")).toHaveLength(5);
  });

  it("draws marks by posture: filled, half, dashed hollow, hollow goal", () => {
    const { container } = render(<Harness concerns={concerns} />);
    const rect = (id: string) => container.querySelector(`[data-key="${id}"] rect`)!;
    expect(rect("loop:told").getAttribute("fill")).toBe("var(--main)");
    expect(rect("loop:inferred").getAttribute("fill")).toBe("url(#half)");
    expect(rect("loop:suspected").getAttribute("stroke-dasharray")).toBe("2 2");
    expect(rect("loop:suspected").getAttribute("fill")).toBe("var(--field)");
    expect(rect("goal:goal").getAttribute("transform")).toMatch(/rotate\(45/);
    expect(rect("goal:goal").getAttribute("fill")).toBe("var(--field)");
  });

  it("gives slipped marks the hot class and marks the most overdue as the leader target", () => {
    const { container } = render(<Harness concerns={concerns} />);
    expect(container.querySelector('[data-key="loop:ana"]')!.classList.contains("hot")).toBe(true);
    expect(container.querySelector('[data-key="goal:goal"]')!.classList.contains("hot")).toBe(true);
    expect(container.querySelector('[data-key="loop:told"]')!.classList.contains("hot")).toBe(false);
    expect(container.querySelectorAll(".pt.lead")).toHaveLength(1);
    expect(container.querySelector(".pt.lead")!.getAttribute("data-key")).toBe("loop:ana");
  });

  it("draws a NOW line and a trail only from a recorded prior", () => {
    const { container } = render(<Harness concerns={concerns} />);
    expect(container.querySelectorAll(".trail")).toHaveLength(1);
    expect(container.querySelector("svg line[stroke='var(--cream)']")).not.toBeNull();
  });

  it("shows a callout on hover and focus", () => {
    const { container } = render(<Harness concerns={concerns} />);
    expect(container.querySelector(".callout")).toBeNull();
    fireEvent.focus(screen.getByRole("button", { name: /Reply to Ana/ }));
    expect(container.querySelector(".callout")!.textContent).toContain("62% sure");
  });

  it("selects on click and on Enter, and toggles off", () => {
    const onSelect = vi.fn();
    const { rerender } = render(<Harness concerns={concerns} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /Reply to Ana/ }));
    expect(onSelect).toHaveBeenLastCalledWith("loop:ana");
    fireEvent.keyDown(screen.getByRole("button", { name: /Ship the thing/ }), { key: "Enter" });
    expect(onSelect).toHaveBeenLastCalledWith("goal:goal");
    rerender(<Harness concerns={concerns} selected="loop:ana" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /Reply to Ana/ }));
    expect(onSelect).toHaveBeenLastCalledWith(null);
  });

  it("states 'not a claim' for a mark with no confidence", () => {
    const { container } = render(<Harness concerns={concerns} />);
    fireEvent.focus(screen.getByRole("button", { name: /Ship the thing/ }));
    expect(container.querySelector(".callout")!.textContent).toContain("not a claim");
  });
});
