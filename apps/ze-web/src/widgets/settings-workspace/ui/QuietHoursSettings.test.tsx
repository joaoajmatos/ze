import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QuietHoursSettings } from "./QuietHoursSettings";

const { useQuietHoursQuery, useUpdateQuietHoursMutation, useAttentionBudgetQuery } = vi.hoisted(() => ({
  useAttentionBudgetQuery: vi.fn(),
  useQuietHoursQuery: vi.fn(),
  useUpdateQuietHoursMutation: vi.fn(),
}));

vi.mock("@/entities/quiet-hours", () => ({
  useQuietHoursQuery,
  useUpdateQuietHoursMutation,
}));

vi.mock("@/entities/notification", () => ({ useAttentionBudgetQuery }));

const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

const base = {
  enabled: false,
  start: null as string | null,
  end: null as string | null,
  timezone: null as string | null,
  active_now: false,
};

function setup({ data = base, mutationError = null }: {
  data?: typeof base;
  mutationError?: unknown;
} = {}) {
  useQuietHoursQuery.mockReturnValue({ data });
  useAttentionBudgetQuery.mockReturnValue({
    data: { max_per_day: 5, held_count: 2 },
  });
  const mutate = vi.fn();
  useUpdateQuietHoursMutation.mockReturnValue({
    mutate,
    isPending: false,
    error: mutationError,
  });
  return { mutate };
}

describe("QuietHoursSettings", () => {
  it("shows the browser timezone when the server value is null", () => {
    setup();
    render(<QuietHoursSettings />);

    expect(screen.getByLabelText("Timezone")).toHaveValue(browserZone);
  });

  it("reads the nudge cap and held count from the attention budget", () => {
    setup({ data: { ...base, enabled: true, active_now: true } });
    render(<QuietHoursSettings />);

    expect(screen.getByText(/at most 5 unprompted nudges/)).toBeInTheDocument();
    expect(screen.getByText("Quiet hours are on now · 2 held")).toBeInTheDocument();
  });

  it("saves the entered values", () => {
    const { mutate } = setup({
      data: {
        ...base,
        enabled: true,
        start: "23:00",
        end: "08:00",
        timezone: "Europe/Lisbon",
      },
    });
    render(<QuietHoursSettings />);

    fireEvent.click(screen.getByText("Save"));

    expect(mutate).toHaveBeenCalledWith({
      enabled: true,
      start: "23:00",
      end: "08:00",
      timezone: "Europe/Lisbon",
    });
  });

  it("shows a 422 message under the field", () => {
    setup({
      data: {
        ...base,
        enabled: true,
        start: "23:00",
        end: "23:00",
        timezone: "Europe/Lisbon",
      },
      mutationError: {
        detail: [
          {
            loc: ["body", "end"],
            msg: "start and end must differ",
            type: "value_error",
          },
        ],
      },
    });
    render(<QuietHoursSettings />);

    expect(screen.getByText("start and end must differ")).toBeInTheDocument();
  });
});
