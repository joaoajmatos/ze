import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Attention } from "./Attention";

const m = vi.hoisted(() => ({
  useQuietHoursQuery: vi.fn(),
  useUpdateQuietHoursMutation: vi.fn(),
  useAttentionBudgetQuery: vi.fn(),
  useNotificationOutcomesQuery: vi.fn(),
}));

vi.mock("@/entities/quiet-hours", () => ({ useQuietHoursQuery: m.useQuietHoursQuery, useUpdateQuietHoursMutation: m.useUpdateQuietHoursMutation }));
vi.mock("@/entities/notification", () => ({ useAttentionBudgetQuery: m.useAttentionBudgetQuery, useNotificationOutcomesQuery: m.useNotificationOutcomesQuery }));

const quiet = { enabled: true, start: "23:00", end: "08:00", timezone: "Europe/Lisbon", active_now: false };
const budget = { used: 2, max_per_day: 5, remaining: 3, window_hours: 24, next_slot_at: "2026-10-31T14:05:00", held_count: 1, quiet_hours_active: false };
const ok = (data: unknown) => ({ data, isLoading: false, isError: false, refetch: vi.fn() });
let mutate: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  mutate = vi.fn();
  m.useQuietHoursQuery.mockReturnValue(ok(quiet));
  m.useUpdateQuietHoursMutation.mockReturnValue({ mutate, isPending: false, error: null });
  m.useAttentionBudgetQuery.mockReturnValue(ok(budget));
  m.useNotificationOutcomesQuery.mockReturnValue(ok([]));
});

describe("Attention", () => {
  it("names where pushes go and links to ntfy", () => {
    render(<Attention />);
    expect(screen.getByText(/pushes go to your ntfy topic/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open ntfy/i })).toHaveAttribute("href", "https://ntfy.sh");
  });

  it("saves the entered quiet hours", () => {
    render(<Attention />);
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(mutate).toHaveBeenCalledWith({ enabled: true, start: "23:00", end: "08:00", timezone: "Europe/Lisbon" });
  });

  it("refuses start equal to end and asks for both times", () => {
    render(<Attention />);
    fireEvent.change(screen.getByLabelText("End"), { target: { value: "23:00" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(mutate).not.toHaveBeenCalled();
    expect(screen.getByText(/start and end must differ/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Start"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(screen.getByText(/set a start and an end/i)).toBeInTheDocument();
  });

  it("requires a timezone when enabled", () => {
    render(<Attention />);
    fireEvent.change(screen.getByLabelText("Timezone"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(mutate).not.toHaveBeenCalled();
    expect(screen.getByText(/choose a timezone/i)).toBeInTheDocument();
  });

  it("clears the times when quiet hours are switched off", () => {
    render(<Attention />);
    fireEvent.click(screen.getByLabelText("Quiet hours"));
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(mutate).toHaveBeenCalledWith({ enabled: false, start: null, end: null, timezone: "Europe/Lisbon" });
  });

  it("shows server field errors", () => {
    m.useUpdateQuietHoursMutation.mockReturnValue({ mutate, isPending: false, error: { detail: [{ loc: ["body", "timezone"], msg: "Unknown timezone" }] } });
    render(<Attention />);
    expect(screen.getByText("Unknown timezone")).toBeInTheDocument();
  });

  it("shows pushes used of the daily maximum, the next slot and the held count", () => {
    render(<Attention />);
    const dots = screen.getByRole("img", { name: /2 of 5 pushes used/i });
    expect(dots.querySelectorAll("i.lit")).toHaveLength(2);
    expect(screen.getByText(/next slot/i)).toHaveTextContent(/next slot \d{2}:\d{2}/i);
    expect(screen.getByText(/1 held/i)).toBeInTheDocument();
  });

  it("omits the next slot when there is none", () => {
    m.useAttentionBudgetQuery.mockReturnValue(ok({ ...budget, next_slot_at: null }));
    render(<Attention />);
    expect(screen.queryByText(/next slot/i)).toBeNull();
  });

  it("lists recent push outcomes that did not land", () => {
    m.useNotificationOutcomesQuery.mockReturnValue(
      ok([
        { id: "1", title: "Stand-up moved", delivery: "held", created_at: "2026-10-31T09:00:00Z" },
        { id: "2", title: "Weekly digest", delivery: "failed", created_at: "2026-10-30T09:00:00Z" },
      ]),
    );
    render(<Attention />);
    const list = screen.getByRole("list", { name: /recent push outcomes/i });
    const rows = within(list).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Stand-up moved");
    expect(rows[0]).toHaveTextContent(/held/i);
    expect(rows[1]).toHaveTextContent(/failed/i);
  });

  it("says so when the push outcomes cannot load", () => {
    m.useNotificationOutcomesQuery.mockReturnValue({ data: undefined, isLoading: false, isError: true, refetch: vi.fn() });
    render(<Attention />);
    expect(screen.getByText(/could not load recent push outcomes/i)).toBeInTheDocument();
  });

  it("shows an error line and no number when the budget route fails", () => {
    m.useAttentionBudgetQuery.mockReturnValue({ data: undefined, isLoading: false, isError: true, refetch: vi.fn() });
    render(<Attention />);
    expect(screen.getByText(/could not load the push budget/i)).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /pushes used/i })).toBeNull();
    expect(screen.queryByText(/\b5\b/)).toBeNull();
  });
});
