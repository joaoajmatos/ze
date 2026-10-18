import type { GoalListItem, WsScreenContext } from "@myguyze/ze-client";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAskOverlay } from "@/features/ask-bar";
import { TryChips } from "./TryChips";

let goals: GoalListItem[] = [];
vi.mock("@/entities/goal", () => ({ useGoalsQuery: () => ({ data: goals }) }));

const goal = (id: string, extra: Partial<GoalListItem> = {}): GoalListItem =>
  ({ id, title: `Goal ${id}`, status: "active", created_at: "2026-10-01T00:00:00Z", last_progress_at: null, ...extra }) as GoalListItem;

beforeEach(() => {
  goals = [];
  useAskOverlay.setState({ draft: "" });
});

describe("TryChips", () => {
  it("sends compose slipping and decisions presets", () => {
    const onSend = vi.fn((_text: string, _context: WsScreenContext) => true);
    render(<TryChips onSend={onSend} />);
    fireEvent.click(screen.getByRole("button", { name: /What's slipping\?/ }));
    fireEvent.click(screen.getByRole("button", { name: /What should I decide today\?/ }));
    expect(onSend).toHaveBeenNthCalledWith(1, "What's slipping?", { origin: "preset", compose: "slipping" });
    expect(onSend).toHaveBeenNthCalledWith(2, "What should I decide today?", { origin: "preset", compose: "decisions" });
  });

  it("hides the goal chip without an active goal", () => {
    goals = [goal("a", { status: "done" })];
    render(<TryChips onSend={vi.fn(() => true)} />);
    expect(screen.getAllByRole("button")).toHaveLength(2);
  });

  it("topic is the active goal with the latest last_progress_at", () => {
    goals = [
      goal("old", { last_progress_at: "2026-10-02T00:00:00Z" }),
      goal("new", { last_progress_at: "2026-10-10T00:00:00Z" }),
      goal("paused", { status: "paused", last_progress_at: "2026-10-16T00:00:00Z" }),
    ];
    const onSend = vi.fn((_text: string, _context: WsScreenContext) => true);
    render(<TryChips onSend={onSend} />);
    fireEvent.click(screen.getByRole("button", { name: /How is Goal new going\?/ }));
    expect(onSend).toHaveBeenCalledWith("How is Goal new going?", { origin: "preset", topic: "Goal new" });
  });

  it("falls back to created_at when last_progress_at is null (a new goal)", () => {
    goals = [
      goal("stale", { last_progress_at: "2026-10-05T00:00:00Z" }),
      goal("fresh", { created_at: "2026-10-17T00:00:00Z", last_progress_at: null }),
    ];
    render(<TryChips onSend={vi.fn(() => true)} />);
    expect(screen.getByRole("button", { name: /How is Goal fresh going\?/ })).toBeTruthy();
  });

  it("keys 1-3 send the chips when nothing is focused and the bar is empty", () => {
    goals = [goal("a")];
    const onSend = vi.fn((_text: string, _context: WsScreenContext) => true);
    render(<TryChips onSend={onSend} />);
    fireEvent.keyDown(document.body, { key: "1" });
    fireEvent.keyDown(document.body, { key: "3" });
    expect(onSend).toHaveBeenCalledTimes(2);
    expect(onSend.mock.calls[1]?.[1]).toMatchObject({ topic: "Goal a" });
  });

  it("ignores keys while an input is focused or the bar has text", () => {
    const onSend = vi.fn((_text: string, _context: WsScreenContext) => true);
    const { rerender } = render(
      <>
        <input aria-label="ask" />
        <TryChips onSend={onSend} />
      </>,
    );
    screen.getByLabelText("ask").focus();
    fireEvent.keyDown(screen.getByLabelText("ask"), { key: "1" });
    (document.activeElement as HTMLElement).blur();
    act(() => useAskOverlay.setState({ draft: "hello" }));
    rerender(
      <>
        <input aria-label="ask" />
        <TryChips onSend={onSend} />
      </>,
    );
    fireEvent.keyDown(document.body, { key: "2" });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("ignores keys while a dialog is open", () => {
    const onSend = vi.fn((_text: string, _context: WsScreenContext) => true);
    render(
      <>
        <div role="dialog" aria-label="d" />
        <TryChips onSend={onSend} />
      </>,
    );
    fireEvent.keyDown(document.body, { key: "1" });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("ignores modified keys and key 3 when there is no goal chip", () => {
    const onSend = vi.fn((_text: string, _context: WsScreenContext) => true);
    render(<TryChips onSend={onSend} />);
    fireEvent.keyDown(document.body, { key: "1", metaKey: true });
    fireEvent.keyDown(document.body, { key: "3" });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables the chips when told to", () => {
    const onSend = vi.fn((_text: string, _context: WsScreenContext) => true);
    render(<TryChips onSend={onSend} disabled />);
    fireEvent.click(screen.getByRole("button", { name: /What's slipping\?/ }));
    fireEvent.keyDown(document.body, { key: "1" });
    expect(onSend).not.toHaveBeenCalled();
  });
});
