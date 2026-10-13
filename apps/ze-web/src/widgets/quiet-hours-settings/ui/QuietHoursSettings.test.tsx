import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QuietHoursSettings } from "./QuietHoursSettings";

const { useQuietHoursQuery, useUpdateQuietHoursMutation } = vi.hoisted(() => ({
  useQuietHoursQuery: vi.fn(),
  useUpdateQuietHoursMutation: vi.fn(),
}));

vi.mock("@/entities/quiet-hours", () => ({
  useQuietHoursQuery,
  useUpdateQuietHoursMutation,
}));

const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

const base = {
  enabled: false,
  start: null as string | null,
  end: null as string | null,
  timezone: null as string | null,
  active_now: false,
  held_count: 0,
  max_discretionary_per_day: 5,
};

function setup({ data = base, mutationError = null }: {
  data?: typeof base;
  mutationError?: unknown;
} = {}) {
  useQuietHoursQuery.mockReturnValue({ data });
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
