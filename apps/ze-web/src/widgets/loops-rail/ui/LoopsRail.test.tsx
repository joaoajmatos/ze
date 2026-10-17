import type { LoopListItem } from "@myguyze/ze-client";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LoopsRail } from "./LoopsRail";

const now = new Date("2026-10-17T12:00:00Z");
const loop = (id: string, extra: Partial<LoopListItem> = {}): LoopListItem => ({
  id, title: `Loop ${id}`, state: "active", claim_kind: "fact", provenance: "email", confidence: 0.74, drift_rationale: null, goal_id: null, reminder_id: null,
  confidence_prior: null, confidence_changed_at: null, drift_deadline: null, confirmed_at: null, created_at: null, updated_at: "2026-10-14T12:00:00Z", promoted: false, source_inflows: ["email"], ...extra,
});

function setup(loops: LoopListItem[], over: Partial<Parameters<typeof LoopsRail>[0]> = {}) {
  const onTransition = vi.fn();
  const onSelect = vi.fn();
  const utils = render(<LoopsRail loops={loops} loading={false} error={false} now={now} offline={false} selected={null} onSelect={onSelect} onTransition={onTransition} busyId={null} {...over} />);
  return { onTransition, onSelect, ...utils };
}

describe("LoopsRail", () => {
  it("shows glyph, state tick, mono readout and the dim line from the posture table", () => {
    const { container } = setup([loop("a", { state: "drifting" })]);
    expect(container.querySelector("i.tick")).not.toBeNull();
    expect(container.querySelector(".glyph")).not.toBeNull();
    expect(screen.getByText("0.74")).toBeTruthy();
    expect(screen.getByText("Drifting · email · 3 d ago")).toBeTruthy();
    expect(container.querySelector(".row.loop.drifting.hot")).not.toBeNull();
  });

  it("draws a Spark and a delta only with a recorded prior", () => {
    const { container } = setup([loop("a", { confidence_prior: 0.8, confidence: 0.74 }), loop("b")]);
    expect(container.querySelectorAll("svg.spark")).toHaveLength(1);
    expect(container.textContent).toContain("▾0.06");
  });

  it("marks a rise as a rise", () => {
    const { container } = setup([loop("a", { confidence_prior: 0.5, confidence: 0.7 })]);
    expect(container.textContent).toContain("▴0.20");
  });

  it("Close and Drop call onTransition for active and drifting rows", () => {
    const { onTransition } = setup([loop("a"), loop("b", { state: "drifting" })]);
    const closes = screen.getAllByRole("button", { name: "Close" });
    fireEvent.click(closes[0]);
    fireEvent.click(screen.getAllByRole("button", { name: "Drop" })[1]);
    expect(onTransition).toHaveBeenNthCalledWith(1, "a", "close");
    expect(onTransition).toHaveBeenNthCalledWith(2, "b", "drop");
  });

  it("has no rows or actions for suspected loops, only a pointer to Needs you", () => {
    setup([loop("s", { state: "suspected" })]);
    expect(screen.queryByRole("button", { name: "Close" })).toBeNull();
    expect(screen.getByText("1 suspected")).toBeTruthy();
  });

  it("selects the field mark from the title", () => {
    const { onSelect } = setup([loop("a")]);
    fireEvent.click(screen.getByRole("button", { name: /Loop a/ }));
    expect(onSelect).toHaveBeenCalledWith("loop:a");
  });

  it("disables actions offline and shows the error and loading states", () => {
    setup([loop("a")], { offline: true });
    expect((screen.getByRole("button", { name: "Close" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("renders the error state", () => {
    setup([], { error: true });
    expect(screen.getByRole("alert").textContent).toContain("Couldn't read");
  });
});
