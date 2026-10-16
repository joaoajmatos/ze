import type { LoopListItem } from "@myguyze/ze-client";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LoopReviewList } from "./LoopReviewList";

const { useLoopsQuery, useLoopTransitionMutation } = vi.hoisted(() => ({
  useLoopsQuery: vi.fn(),
  useLoopTransitionMutation: vi.fn(),
}));

vi.mock("@/entities/loop", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/entities/loop")>();
  return {
    ...actual,
    useLoopsQuery,
    useLoopTransitionMutation,
  };
});

const suspectedLoop: LoopListItem = {
  id: "loop-1",
  title: "Renew passport before the trip",
  state: "suspected",
  claim_kind: "suspicion",
  provenance: "conversation",
  confidence: 0.35,
  drift_rationale: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  promoted: false,
  source_inflows: [],
};

const activeLoop: LoopListItem = {
  ...suspectedLoop,
  id: "loop-2",
  title: "Follow up with the accountant",
  state: "active",
  provenance: "user_declared",
  confidence: 0.9,
};

const driftingLoop: LoopListItem = {
  ...suspectedLoop,
  id: "loop-3",
  title: "Book the dentist appointment",
  state: "drifting",
  provenance: "email",
  confidence: 0.5,
};

const suspectedLoop2: LoopListItem = {
  ...suspectedLoop,
  id: "loop-4",
  title: "Chase the insurance refund",
  state: "suspected",
  confidence: 0.4,
};

const promotedLoop: LoopListItem = {
  ...activeLoop,
  id: "loop-5",
  title: "Sort out the deposit with the landlord",
  promoted: true,
  source_inflows: ["conversation", "email"],
};

function setup(loops: LoopListItem[], mutate = vi.fn()) {
  useLoopsQuery.mockReturnValue({
    data: loops,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  });
  useLoopTransitionMutation.mockReturnValue({ mutate, isPending: false });
  return mutate;
}

function sectionFor(heading: string): HTMLElement {
  const section = screen.getByText(heading).closest("section");
  if (!section) throw new Error(`no section for ${heading}`);
  return section;
}

describe("LoopReviewList", () => {
  it("shows the empty state when there are no loops", () => {
    setup([]);
    render(<LoopReviewList />);
    expect(screen.getByText("No open loops right now.")).toBeInTheDocument();
  });

  it("visibly distinguishes suspected from active rows", () => {
    setup([suspectedLoop, activeLoop]);
    render(<LoopReviewList />);

    expect(screen.getByText("Suspected")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("groups suspected loops under 'Needs your OK' above tracking loops", () => {
    setup([activeLoop, suspectedLoop, driftingLoop, suspectedLoop2]);
    render(<LoopReviewList />);

    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(["Needs your OK", "Tracking"]);

    const needsOk = sectionFor("Needs your OK");
    expect(within(needsOk).getByText(suspectedLoop.title)).toBeInTheDocument();
    expect(within(needsOk).getByText(suspectedLoop2.title)).toBeInTheDocument();
    expect(within(needsOk).queryByText(activeLoop.title)).toBeNull();

    const tracking = sectionFor("Tracking");
    expect(within(tracking).getByText(activeLoop.title)).toBeInTheDocument();
    expect(within(tracking).getByText(driftingLoop.title)).toBeInTheDocument();
    expect(within(tracking).queryByText(suspectedLoop.title)).toBeNull();
  });

  it("offers Keep and Drop on suspected rows and no Close", () => {
    setup([suspectedLoop, suspectedLoop2]);
    render(<LoopReviewList />);

    const needsOk = sectionFor("Needs your OK");
    expect(within(needsOk).getAllByText("Keep")).toHaveLength(2);
    expect(within(needsOk).getAllByText("Drop")).toHaveLength(2);
    expect(within(needsOk).queryByText("Close")).toBeNull();
  });

  it("offers Close and Drop on active and drifting rows", () => {
    setup([activeLoop, driftingLoop]);
    render(<LoopReviewList />);

    const tracking = sectionFor("Tracking");
    expect(within(tracking).getAllByText("Close")).toHaveLength(2);
    expect(within(tracking).getAllByText("Drop")).toHaveLength(2);
    expect(within(tracking).queryByText("Keep")).toBeNull();
  });

  it("calls the transition mutation with confirm on Keep click", () => {
    const mutate = setup([suspectedLoop]);
    render(<LoopReviewList />);

    fireEvent.click(screen.getByText("Keep"));

    expect(mutate).toHaveBeenCalledWith({ loopId: "loop-1", kind: "confirm" });
  });

  it("calls the transition mutation with drop on click", () => {
    const mutate = setup([suspectedLoop]);
    render(<LoopReviewList />);

    fireEvent.click(screen.getByText("Drop"));

    expect(mutate).toHaveBeenCalledWith({ loopId: "loop-1", kind: "drop" });
  });

  it("hides the 'Needs your OK' section when only tracking loops exist", () => {
    setup([activeLoop, driftingLoop]);
    render(<LoopReviewList />);

    expect(screen.queryByText("Needs your OK")).toBeNull();
  });

  it("hides the 'Tracking' section when only suspected loops exist", () => {
    setup([suspectedLoop, suspectedLoop2]);
    render(<LoopReviewList />);

    expect(screen.queryByText("Tracking")).toBeNull();
  });

  it("shows the 'Promoted · seen in' line for a promoted loop", () => {
    setup([promotedLoop]);
    render(<LoopReviewList />);

    expect(screen.getByText("Promoted · seen in: chat, email")).toBeInTheDocument();
  });

  it("shows no promoted line for loops that were not promoted", () => {
    setup([suspectedLoop, activeLoop, driftingLoop]);
    render(<LoopReviewList />);

    expect(screen.queryByText(/Promoted/)).toBeNull();
  });
});
