import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { concern, day, NOW } from "../lib/fixtures";
import { FieldList } from "./FieldList";

const concerns = [
  concern("late", { title: "Reply to Ana", rank: 1, state: "drifting", slipped: true, due: day(-3), confidence: 0.62 }),
  concern("soon", { title: "Call dentist", rank: 2, due: day(2), confidence: 0.8, provenance: "user_declared" }),
  concern("far", { title: "Plan trip", rank: 3, due: day(20), confidence: 0.5, claimKind: "inference" }),
  concern("open", { title: "Learn Rust", rank: 4, confidence: 0.4, state: "suspected" }),
  concern("goal", { kind: "goal", key: "goal:goal", title: "Ship v1", rank: 5, slipped: true, state: "active", confidence: null }),
];

describe("FieldList", () => {
  it("groups by band: Slipped (a stuck goal with no deadline included), This week, Later, No deadline", () => {
    render(<FieldList concerns={concerns} now={NOW} selected={null} onSelect={() => {}} />);
    const names = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(names).toEqual(["Slipped · 2", "This week · 1", "Later · 1", "No deadline · 1"]);
  });

  it("ranks within a band and shows the posture vocabulary, never a raw enum or a made-up confidence", () => {
    const { container } = render(<FieldList concerns={concerns} now={NOW} selected={null} onSelect={() => {}} />);
    const text = container.textContent ?? "";
    expect(text).toContain("62%");
    expect(text).toContain("stuck");
    expect(text).toContain("· told");
    expect(text).not.toMatch(/user_declared|awaiting_gate|drifting_/);
    const goalRow = screen.getByRole("button", { name: /Ship v1/ });
    expect(goalRow.textContent).toContain("—");
    expect(goalRow.textContent).not.toContain("50%");
  });

  it("lets a slipped row pulse, but not under reduced motion", () => {
    const { container, unmount } = render(<FieldList concerns={concerns} now={NOW} selected={null} onSelect={() => {}} />);
    expect(container.querySelectorAll("li.slip-pulse")).toHaveLength(2);
    unmount();
    const mq = vi.spyOn(window, "matchMedia").mockImplementation((q) => ({ matches: q.includes("reduce"), media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, onchange: null, dispatchEvent: () => false }) as MediaQueryList);
    const again = render(<FieldList concerns={concerns} now={NOW} selected={null} onSelect={() => {}} />);
    expect(again.container.querySelectorAll("li.slip-pulse")).toHaveLength(0);
    expect(again.container.querySelectorAll("li.hot")).toHaveLength(2);
    mq.mockRestore();
  });

  it("selects and deselects a row", () => {
    const onSelect = vi.fn();
    const { rerender } = render(<FieldList concerns={concerns} now={NOW} selected={null} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /Reply to Ana/ }));
    expect(onSelect).toHaveBeenLastCalledWith("loop:late");
    rerender(<FieldList concerns={concerns} now={NOW} selected="loop:late" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /Reply to Ana/ }));
    expect(onSelect).toHaveBeenLastCalledWith(null);
  });
});
