import type { MilestoneResponse } from "@myguyze/ze-client";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const narrow = vi.hoisted(() => ({ value: false }));
vi.mock("@/shared/lib", async (orig) => ({ ...(await orig<object>()), useNarrow: () => narrow.value }));

import { MilestoneField } from "./MilestoneField";

const m = (o: Partial<MilestoneResponse>): MilestoneResponse => ({
  id: "m1", title: "Draft", description: "", sequence: 1, status: "pending", output: null, reuse_hint: null,
  completed_at: null, created_at: "2026-10-01T00:00:00Z", ...o,
});

describe("MilestoneField", () => {
  beforeEach(() => (narrow.value = false));

  it("places marks by time: completed time for done, created time otherwise", () => {
    const { container } = render(
      <MilestoneField
        milestones={[
          m({ id: "a", sequence: 1, status: "completed", completed_at: "2026-10-03T00:00:00Z" }),
          m({ id: "b", sequence: 2, title: "Ship", status: "pending", created_at: "2026-10-11T00:00:00Z" }),
        ]}
      />,
    );
    const xs = [...container.querySelectorAll("g.mark > rect:last-of-type")].map((r) => Number(r.getAttribute("x")));
    expect(xs[0]).toBeLessThan(xs[1]);
  });

  it("fills done, rings active, leaves pending hollow", () => {
    const { container } = render(
      <MilestoneField milestones={[m({ id: "a", status: "completed", completed_at: "2026-10-02T00:00:00Z" }), m({ id: "b", sequence: 2, status: "in_progress" }), m({ id: "c", sequence: 3, status: "pending" })]} />,
    );
    const groups = [...container.querySelectorAll("g.mark")];
    expect(groups[0].querySelector("rect")!.getAttribute("fill")).toBe("var(--main)");
    expect(groups[1].querySelectorAll("rect")).toHaveLength(2);
    expect(groups[2].querySelector("rect")!.getAttribute("fill")).toBe("none");
  });

  it("labels every mark with its title and state in words", () => {
    render(<MilestoneField milestones={[m({ status: "in_progress" })]} />);
    expect(screen.getByRole("img", { name: "Draft: in progress" })).toBeInTheDocument();
  });

  it("renders an ordered list on phones", () => {
    narrow.value = true;
    render(<MilestoneField milestones={[m({ id: "b", sequence: 2, title: "Second" }), m({ id: "a", title: "First", status: "completed" })]} />);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("First");
    expect(items[1]).toHaveTextContent("Second");
    expect(screen.getByText("done")).toBeInTheDocument();
  });

  it("says so when there are none", () => {
    render(<MilestoneField milestones={[]} />);
    expect(screen.getByText("No milestones yet.")).toBeInTheDocument();
  });
});
