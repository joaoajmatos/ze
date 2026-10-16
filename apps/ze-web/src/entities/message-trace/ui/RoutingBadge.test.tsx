import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RoutingBadge } from "./RoutingBadge";

const base = {
  agent: "companion",
  routingMethod: "embedding",
  confidence: 0.9,
  scoreGap: 0.2,
  isCompound: false,
  subtasks: [],
  totalDurationMs: 0,
};

function tierProps(tier: "simple" | "full", decided_by: string) {
  return { tier: { agent: "companion", tier, decided_by, model: "m" } };
}

describe("RoutingBadge tier line", () => {
  it.each([
    ["simple", "system_one", "Light model · System One"],
    ["full", "system_one", "Full model · System One"],
    ["full", "off", "Full model · tiering off"],
    ["full", "uncalibrated", "Full model · tiering not calibrated"],
    ["full", "skip", "Full model · System One unavailable"],
    ["full", "invalid_answer", "Full model · System One unavailable"],
    ["full", "compound", "Full model · multi-agent turn"],
  ] as const)("renders %s / %s as %s", (tier, decided_by, text) => {
    render(<RoutingBadge {...base} {...tierProps(tier, decided_by)} />);
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it("renders nothing for no_simple_model", () => {
    render(<RoutingBadge {...base} {...tierProps("full", "no_simple_model")} />);
    expect(screen.queryByText(/model ·/)).not.toBeInTheDocument();
  });

  it("renders nothing when the tier is absent", () => {
    render(<RoutingBadge {...base} />);
    expect(screen.queryByText(/model ·/)).not.toBeInTheDocument();
  });

  it("renders nothing when the tier is null", () => {
    render(<RoutingBadge {...base} tier={null} />);
    expect(screen.queryByText(/model ·/)).not.toBeInTheDocument();
  });
});
