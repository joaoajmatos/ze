import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { SkillsSection } from "./SkillsSection";

type SkillsUsed = NonNullable<WsTraceUpdateFrame["skills_used"]>;

function skill(overrides: Record<string, unknown> = {}): SkillsUsed[number] {
  return {
    skill_id: "s1",
    name: "deep-research",
    source: "url",
    trigger: "auto",
    similarity: 0.62,
    ...overrides,
  } as SkillsUsed[number];
}

describe("SkillsSection", () => {
  it("shows the below floor mark only when below_floor is true", () => {
    render(<SkillsSection skillsUsed={[skill({ below_floor: true })]} />);
    expect(screen.getByText("below floor")).toBeInTheDocument();
  });

  it("keeps the existing badges and no mark when below_floor is false", () => {
    render(<SkillsSection skillsUsed={[skill({ below_floor: false })]} />);
    expect(screen.getByText("deep-research")).toBeInTheDocument();
    expect(screen.getByText("url")).toBeInTheDocument();
    expect(screen.getByText("auto")).toBeInTheDocument();
    expect(screen.getByText("62%")).toBeInTheDocument();
    expect(screen.queryByText("below floor")).not.toBeInTheDocument();
  });

  it("shows no mark when below_floor is absent", () => {
    render(<SkillsSection skillsUsed={[skill()]} />);
    expect(screen.queryByText("below floor")).not.toBeInTheDocument();
  });
});
