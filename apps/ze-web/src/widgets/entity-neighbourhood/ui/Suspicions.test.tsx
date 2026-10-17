import type { HypothesisItem } from "@myguyze/ze-client";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Suspicions } from "./Suspicions";

const { useHypothesesQuery, mutate } = vi.hoisted(() => ({ useHypothesesQuery: vi.fn(), mutate: vi.fn() }));
vi.mock("@/entities/hypothesis", () => ({
  useHypothesesQuery,
  useHypothesisFeedbackMutation: () => ({ mutate, isPending: false }),
}));

const hyp = (over: Partial<HypothesisItem> = {}): HypothesisItem => ({
  id: "h1",
  summary: "Ada's trips follow her launch weeks",
  narrative: "n",
  relation: "causal_guess",
  confidence: 0.42,
  claim_kind: "suspicion",
  evidence: [{ kind: "fact", id: "f1", label: "Ada flew to Lisbon" }],
  entities: [{ id: "e1", name: "Ada" }],
  surfaced: false,
  feedback: null,
  confirmed: false,
  ...over,
} as HypothesisItem);

describe("Suspicions", () => {
  beforeEach(() => vi.clearAllMocks());

  it("asks for hypotheses about the entity, dismissed ones included", () => {
    useHypothesesQuery.mockReturnValue({ data: [hyp()] });
    render(<Suspicions entityId="e1" />);
    expect(useHypothesesQuery).toHaveBeenCalledWith({ state: "all", entityId: "e1" });
  });

  it("shows I suspect, posture, relation in words and evidence labels", () => {
    useHypothesesQuery.mockReturnValue({ data: [hyp()] });
    const { container } = render(<Suspicions entityId="e1" />);
    expect(screen.getByRole("region", { name: /i suspect/i })).toBeInTheDocument();
    expect(screen.getByText("Ada's trips follow her launch weeks")).toBeInTheDocument();
    expect(screen.getByText("suspected")).toBeInTheDocument();
    expect(screen.getByText(/my guess at a cause/i)).toBeInTheDocument();
    expect(screen.getByText(/Ada flew to Lisbon/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/causal_guess/);
  });

  it("sends Useful, Not relevant and Mute", () => {
    useHypothesesQuery.mockReturnValue({ data: [hyp()] });
    render(<Suspicions entityId="e1" />);
    fireEvent.click(screen.getByRole("button", { name: /useful/i }));
    expect(mutate).toHaveBeenCalledWith({ hypothesisId: "h1", feedback: "useful" });
    fireEvent.click(screen.getByRole("button", { name: /not relevant/i }));
    expect(mutate).toHaveBeenCalledWith({ hypothesisId: "h1", feedback: "not_relevant" });
    fireEvent.click(screen.getByRole("button", { name: /mute/i }));
    expect(mutate).toHaveBeenCalledWith({ hypothesisId: "h1", feedback: "muted" });
  });

  it("lets a dismissed hypothesis be cleared", () => {
    useHypothesesQuery.mockReturnValue({ data: [hyp({ feedback: "not_relevant" })] });
    render(<Suspicions entityId="e1" />);
    expect(screen.getByText(/dismissed/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /clear/i }));
    expect(mutate).toHaveBeenCalledWith({ hypothesisId: "h1", feedback: null });
  });

  it("is absent when there is nothing to say", () => {
    useHypothesesQuery.mockReturnValue({ data: [] });
    const { container } = render(<Suspicions entityId="e1" />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("Suspicions chat about", () => {
  it("chats about a suspicion with a hypothesis ref", () => {
    useHypothesesQuery.mockReturnValue({ data: [hyp()] });
    const onChatAbout = vi.fn();
    render(<Suspicions entityId="e1" onChatAbout={onChatAbout} />);
    fireEvent.click(screen.getByRole("button", { name: "Chat about this suspicion" }));
    expect(onChatAbout).toHaveBeenCalledWith(
      { kind: "hypothesis", id: "h1", label: "Ada's trips follow her launch weeks", component: "suspicion_row" },
      expect.any(Element),
    );
  });
});
