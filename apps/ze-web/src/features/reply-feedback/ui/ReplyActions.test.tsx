import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { MessageFeedback } from "@/entities/message-feedback";
import { ReplyActions } from "./ReplyActions";

const { mutate } = vi.hoisted(() => ({ mutate: vi.fn() }));
vi.mock("@/entities/message-feedback", () => ({
  useSetMessageFeedbackMutation: () => ({ mutate }),
}));

function view(current: "up" | "down" | null = null): MessageFeedback {
  return {
    message_id: "m1",
    current,
    history: [],
    retry: { available: true, reason_code: null, reason_text: null },
    replaces: null,
    replaced_by: null,
    trace_present: true,
  };
}

function renderActions(feedback: MessageFeedback | undefined) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <ReplyActions messageId="m1" feedback={feedback} />
    </QueryClientProvider>,
  );
}

describe("ReplyActions", () => {
  beforeEach(() => mutate.mockReset());

  it("names both thumbs and reflects the current rating via aria-pressed", () => {
    renderActions(view("up"));
    expect(screen.getByRole("button", { name: "Good reply" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Bad reply" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("rates up when unrated", () => {
    renderActions(view());
    fireEvent.click(screen.getByRole("button", { name: "Good reply" }));
    expect(mutate.mock.calls[0][0]).toMatchObject({ messageId: "m1", rating: "up" });
    expect(mutate.mock.calls[0][0].idempotencyKey).toBeTruthy();
  });

  it("clears when the active thumb is pressed again", () => {
    renderActions(view("down"));
    fireEvent.click(screen.getByRole("button", { name: "Bad reply" }));
    expect(mutate.mock.calls[0][0]).toMatchObject({ rating: "none" });
  });

  it("switches to the other thumb", () => {
    renderActions(view("up"));
    fireEvent.click(screen.getByRole("button", { name: "Bad reply" }));
    expect(mutate.mock.calls[0][0]).toMatchObject({ rating: "down" });
  });

  it("shows a short error when saving fails", async () => {
    mutate.mockImplementationOnce((_args, opts) => opts.onError(new Error("x")));
    renderActions(view());
    fireEvent.click(screen.getByRole("button", { name: "Good reply" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/couldn't save/i));
  });

  it("is keyboard operable: thumbs are real buttons in tab order", () => {
    renderActions(view());
    const btn = screen.getByRole("button", { name: "Good reply" });
    btn.focus();
    expect(btn).toHaveFocus();
    expect(btn).not.toHaveAttribute("tabindex", "-1");
  });

  it("disables thumbs until feedback state has loaded", () => {
    renderActions(undefined);
    expect(screen.getByRole("button", { name: "Good reply" })).toBeDisabled();
  });
});
