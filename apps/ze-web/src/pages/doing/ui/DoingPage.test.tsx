import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const publisher = vi.hoisted(() => vi.fn());
const q = (data: unknown) => ({ data, isLoading: false, isError: false, dataUpdatedAt: 1, refetch: vi.fn() });
vi.mock("@/widgets/doing-needs-you", () => ({ DoingNeedsYou: () => <div data-testid="needs" /> }));
vi.mock("@/widgets/goals-board", () => ({ GoalsBoard: () => <div data-testid="goals" /> }));
vi.mock("@/widgets/workflows-board", () => ({ WorkflowsBoard: () => <div data-testid="workflows" /> }));
vi.mock("@/widgets/runs", () => ({ Runs: () => <div data-testid="runs" /> }));
vi.mock("@/widgets/skills-queue", () => ({ SkillsQueue: () => <div data-testid="skills" /> }));
vi.mock("@/features/answer-gate", () => ({ useAnswerGate: () => ({}) }));
vi.mock("@/features/ask-bar", () => ({ useChatAbout: () => vi.fn() }));
vi.mock("@/entities/confirmation", () => ({ useHeldWritesQuery: () => q([]) }));
vi.mock("@/entities/goal", () => ({ useGoalsQuery: () => q([{ id: "g1", title: "Goal", gate_id: "x", stuck_since: null }]) }));
vi.mock("@/entities/skill", () => ({ useSkillsQuery: () => q([]) }));
vi.mock("@/entities/workflow", () => ({ useWorkflowsQuery: () => q([{ id: "w1", name: "Flow" }]), useLatestExecutionsQuery: () => ({ byWorkflow: {}, loading: false, error: false }) }));
vi.mock("@/entities/workspace", () => ({ useWorkspaceRunsQuery: () => q([{ id: "r1", command: "ls" }]), useWorkspaceQuery: () => q({ available: true }) }));
vi.mock("@/entities/screen-context", () => ({ useScreenPublisher: (...a: unknown[]) => publisher(...a) }));
vi.mock("@/shared/api", () => ({ useWsStore: (sel: (s: { isConnected: boolean }) => unknown) => sel({ isConnected: true }) }));

import { DoingPage } from "./DoingPage";

const view = (hash = "") =>
  render(
    <MemoryRouter initialEntries={[`/doing${hash}`]}>
      <DoingPage />
    </MemoryRouter>,
  );

describe("DoingPage", () => {
  beforeEach(() => publisher.mockClear());

  it("orders the modules Needs you → Goals → Workflows → Runs → Skills in the DOM (the phone order)", () => {
    const { container } = view();
    const ids = [...container.querySelectorAll("[data-testid]")].map((e) => e.getAttribute("data-testid"));
    expect(ids).toEqual(["needs", "goals", "workflows", "runs", "skills"]);
  });

  it("puts Needs you and Goals left, Workflows and Runs centre, Skills right on desktop", () => {
    const { container } = view();
    const cols = [...container.querySelectorAll(".doing-grid > .doing-col")];
    expect(cols).toHaveLength(3);
    expect(cols[0].querySelector('[data-testid="needs"]') && cols[0].querySelector('[data-testid="goals"]')).toBeTruthy();
    expect(cols[1].querySelector('[data-testid="workflows"]') && cols[1].querySelector('[data-testid="runs"]')).toBeTruthy();
    expect(cols[2].querySelector('[data-testid="skills"]')).toBeTruthy();
  });

  it("exposes hint targets goals, workflows, runs and skills", () => {
    const { container } = view();
    for (const id of ["goals", "workflows", "runs", "skills"]) expect(container.querySelector(`#${id}`)).not.toBeNull();
  });

  it("publishes visible goals, workflows and runs", () => {
    view();
    const pub = publisher.mock.calls[0][0] as { visible: { kind: string; id: string }[] };
    expect(pub.visible).toEqual(expect.arrayContaining([expect.objectContaining({ kind: "goal", id: "g1" }), expect.objectContaining({ kind: "workflow", id: "w1" }), expect.objectContaining({ kind: "workspace_run", id: "r1" })]));
  });
});
