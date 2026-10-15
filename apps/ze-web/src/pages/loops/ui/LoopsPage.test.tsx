import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LoopsPage } from "./LoopsPage";

vi.mock("@/widgets/loop-review", () => ({
  LoopReviewList: () => <div data-testid="loop-review-list" />,
}));

describe("LoopsPage", () => {
  it("renders the loop review list", () => {
    render(<LoopsPage />);
    expect(screen.getByTestId("loop-review-list")).toBeInTheDocument();
  });
});
