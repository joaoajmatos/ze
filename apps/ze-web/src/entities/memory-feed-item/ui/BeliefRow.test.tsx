import type { MemoryFeedItem } from "@myguyze/ze-client";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BeliefRow } from "./BeliefRow";

const fact = (over: Partial<MemoryFeedItem> = {}): MemoryFeedItem => ({
  id: "f1",
  type: "fact",
  key: "works_at",
  value: "Acme",
  confidence: 0.74,
  reviewed: false,
  contradicted: false,
  provenance: "raw",
  claim_kind: "identity",
  summary: null,
  prompt_snippet: null,
  agent: "companion",
  created_at: "2026-10-14T08:00:00Z",
  ...over,
});

const handlers = () => ({ onKeep: vi.fn(), onDrop: vi.fn(), onEdit: vi.fn() });

describe("BeliefRow", () => {
  it("shows sentence, kind, confidence, source and since without the raw key", () => {
    const { container } = render(<ul><BeliefRow item={fact()} {...handlers()} now={new Date("2026-10-17T12:00:00Z")} /></ul>);
    expect(screen.getByText("Works at Acme")).toBeInTheDocument();
    expect(screen.getByText("told")).toBeInTheDocument();
    expect(screen.getByText("0.74")).toBeInTheDocument();
    expect(screen.getByText(/you told me, via companion/)).toBeInTheDocument();
    expect(screen.getByText(/since 3 days ago/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/works_at/);
    expect(container.querySelector(".glyph")).not.toBeNull();
  });

  it("takes the glyph from the claim kind", () => {
    const { container } = render(<ul><BeliefRow item={fact({ claim_kind: "suspicion" })} {...handlers()} /></ul>);
    expect(container.querySelector(".glyph.suspected")).not.toBeNull();
    expect(screen.getByText("suspected")).toBeInTheDocument();
  });

  it("marks reviewed and contradicted beliefs", () => {
    render(<ul><BeliefRow item={fact({ reviewed: true, contradicted: true })} {...handlers()} /></ul>);
    expect(screen.getByText("kept")).toBeInTheDocument();
    expect(screen.getByText("contradicted")).toBeInTheDocument();
  });

  it("calls Keep, Drop and Edit", () => {
    const h = handlers();
    render(<ul><BeliefRow item={fact()} {...h} /></ul>);
    fireEvent.click(screen.getByRole("button", { name: /keep this/i }));
    expect(h.onKeep).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /drop this/i }));
    expect(h.onDrop).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /edit this/i }));
    const input = screen.getByRole("textbox", { name: /new value/i });
    fireEvent.change(input, { target: { value: "Globex" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(h.onEdit).toHaveBeenCalledWith("Globex");
  });

  it("gives every control the 44 px control class", () => {
    render(<ul><BeliefRow item={fact()} {...handlers()} /></ul>);
    for (const b of screen.getAllByRole("button")) expect(b.className).toContain("ctl");
  });
});
