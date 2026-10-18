import type { GoalListItem, WsScreenContext } from "@myguyze/ze-client";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAskOverlay } from "@/features/ask-bar";
import type { UiContribution } from "@/entities/ui-manifest";
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

  describe("plugin presets", () => {
    const preset = (id: string, prompt: string): UiContribution =>
      ({ id, plugin: "p", kind: "preset", label: prompt, icon: "box", prompt, priority: 100 }) as UiContribution;
    const sends = () => vi.fn((_text: string, _context: WsScreenContext) => true);

    it("renders presets after the core chips, at most two, in order", () => {
      render(<TryChips onSend={sends()} presets={[preset("a.one", "First?"), preset("b.two", "Second?"), preset("c.three", "Third?")]} />);
      const labels = screen.getAllByRole("button").map((b) => b.textContent ?? "");
      expect(labels).toHaveLength(4);
      expect(labels[2]).toContain("First?");
      expect(labels[3]).toContain("Second?");
      expect(screen.queryByRole("button", { name: /Third\?/ })).toBeNull();
    });

    it("continues the visible numbering and keys: 3-4 with no goal", () => {
      const onSend = sends();
      render(<TryChips onSend={onSend} presets={[preset("a.one", "First?"), preset("b.two", "Second?")]} />);
      expect(screen.getByRole("button", { name: /First\?/ })).toHaveTextContent("3");
      fireEvent.keyDown(document.body, { key: "3" });
      fireEvent.keyDown(document.body, { key: "4" });
      fireEvent.keyDown(document.body, { key: "5" });
      expect(onSend).toHaveBeenCalledTimes(2);
      expect(onSend).toHaveBeenNthCalledWith(1, "First?", { origin: "preset" });
      expect(onSend).toHaveBeenNthCalledWith(2, "Second?", { origin: "preset" });
    });

    it("continues as 4-5 with an active goal", () => {
      goals = [goal("a")];
      const onSend = sends();
      render(<TryChips onSend={onSend} presets={[preset("a.one", "First?"), preset("b.two", "Second?")]} />);
      expect(screen.getByRole("button", { name: /First\?/ })).toHaveTextContent("4");
      fireEvent.keyDown(document.body, { key: "5" });
      fireEvent.keyDown(document.body, { key: "6" });
      expect(onSend).toHaveBeenCalledTimes(1);
      expect(onSend).toHaveBeenCalledWith("Second?", { origin: "preset" });
    });

    it("sends the prompt with origin preset on click", () => {
      const onSend = sends();
      render(<TryChips onSend={onSend} presets={[preset("a.one", "First?")]} />);
      fireEvent.click(screen.getByRole("button", { name: /First\?/ }));
      expect(onSend).toHaveBeenCalledWith("First?", { origin: "preset" });
    });

    it("keys chips by id, so a repeated prompt raises no key warning", () => {
      const error = vi.spyOn(console, "error").mockImplementation(() => {});
      render(<TryChips onSend={sends()} presets={[preset("a.one", "Same?"), preset("b.two", "Same?")]} />);
      expect(error).not.toHaveBeenCalled();
      error.mockRestore();
    });

    it("disables presets when told to", () => {
      const onSend = sends();
      render(<TryChips onSend={onSend} disabled presets={[preset("a.one", "First?")]} />);
      fireEvent.click(screen.getByRole("button", { name: /First\?/ }));
      fireEvent.keyDown(document.body, { key: "3" });
      expect(onSend).not.toHaveBeenCalled();
    });

    it("adds no chip without presets", () => {
      render(<TryChips onSend={sends()} presets={[]} />);
      expect(screen.getAllByRole("button")).toHaveLength(2);
    });
  });
});
