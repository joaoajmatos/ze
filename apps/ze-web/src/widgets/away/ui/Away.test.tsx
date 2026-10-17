import type { AttentionBudgetResponse, NotificationItem } from "@myguyze/ze-client";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Away } from "./Away";

const now = new Date("2026-10-17T12:00:00Z");
const note = (id: string, extra: Partial<NotificationItem> = {}) =>
  ({ id, title: `Note ${id}`, created_at: "2026-10-17T09:00:00Z", delivered_at: "2026-10-17T09:00:00Z", target_type: "open_loop", target_id: "l1", target_parent_id: null, ...extra }) as NotificationItem;
const budget = (extra: Partial<AttentionBudgetResponse> = {}) => ({ used: 3, max_per_day: 5, remaining: 2, window_hours: 24, next_slot_at: null, held_count: 0, quiet_hours_active: false, ...extra }) as AttentionBudgetResponse;
const run = (job_id: string, label: string, last_status: "ok" | "error" | "running" = "ok") => ({ job_id, label, last_status, last_started_at: "2026-10-17T08:00:00Z", last_finished_at: "2026-10-17T08:01:00Z" });

function setup(over: Partial<Parameters<typeof Away>[0]> = {}) {
  return render(
    <MemoryRouter>
      <Away notifications={[]} jobRuns={[]} budget={null} loading={false} error={false} now={now} {...over} />
    </MemoryRouter>,
  );
}

describe("Away", () => {
  it("lists notifications with one action through notificationHref", () => {
    setup({ notifications: [note("1"), note("2", { target_type: "martian" })] });
    const links = screen.getAllByRole("link", { name: "Open" });
    expect(links).toHaveLength(1);
    expect(links[0].getAttribute("href")).toBe("/?focus=loop:l1");
  });

  it("shows only visible job runs, with their labels", () => {
    setup({ jobRuns: [run("morning_briefing", "Morning briefing"), run("goal_advance_sweep", "Goal progress check", "error")] });
    expect(screen.getByText("Morning briefing")).toBeTruthy();
    expect(screen.getByText("failed")).toBeTruthy();
    expect(screen.queryByText(/checkpoint/i)).toBeNull();
  });

  it("reads the budget, with the next slot only when present", () => {
    const { rerender } = setup({ budget: budget() });
    expect(screen.getByText("3 of 5 used")).toBeTruthy();
    expect(screen.queryByText(/Next slot/)).toBeNull();
    rerender(
      <MemoryRouter>
        <Away notifications={[]} jobRuns={[]} budget={budget({ next_slot_at: "2026-10-17T14:20:00Z" })} loading={false} error={false} now={now} />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Next slot/)).toBeTruthy();
  });

  it("chats about a notification and about a workflow execution with the right ref", () => {
    const onChatAbout = vi.fn();
    setup({ notifications: [note("1"), note("2", { target_type: "workflow_execution", target_id: "e1", target_parent_id: "w1" })], onChatAbout });
    const chips = screen.getAllByRole("button", { name: /Chat about/ });
    fireEvent.click(chips[0]);
    fireEvent.click(chips[1]);
    expect(onChatAbout).toHaveBeenNthCalledWith(1, { kind: "notification", id: "1" }, null);
    expect(onChatAbout).toHaveBeenNthCalledWith(2, { kind: "workflow_execution", id: "e1", parent_id: "w1" }, null);
  });

  it("says Quiet when nothing happened, and shows the error state", () => {
    const { unmount } = setup();
    expect(screen.getByText("Quiet.")).toBeTruthy();
    unmount();
    setup({ error: true });
    expect(screen.getByRole("alert").textContent).toContain("Couldn't read");
  });
});
