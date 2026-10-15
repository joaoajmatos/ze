import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { RetryEligibility } from "@/entities/message-feedback";
import { RetryButton } from "./RetryButton";

const OK: RetryEligibility = { available: true, reason_code: null, reason_text: null, plan: [] };
const WITH_PLAN: RetryEligibility = {
  ...OK,
  plan: [
    {
      entry_id: "e1",
      tool: "set_reminder",
      effect_phrase: "set a reminder",
      undo_note: "Does not recall a notification already shown",
    },
  ],
};
const BLOCKED: RetryEligibility = {
  available: false,
  reason_code: "not_undoable",
  reason_text: "This reply set a reminder.",
};

function renderButton(overrides: Partial<React.ComponentProps<typeof RetryButton>> = {}) {
  const onRetry = vi.fn();
  render(
    <RetryButton
      eligibility={OK}
      isLatest
      connected
      busy={false}
      retrying={false}
      onRetry={onRetry}
      {...overrides}
    />,
  );
  return onRetry;
}

describe("RetryButton", () => {
  it("retries when available", () => {
    const onRetry = renderButton();
    fireEvent.click(screen.getByRole("button", { name: "Retry reply" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("exposes the server reason through aria-describedby and never fires", () => {
    const onRetry = renderButton({ eligibility: BLOCKED });
    const button = screen.getByRole("button", { name: "Retry reply" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toHaveAccessibleDescription("This reply set a reminder.");
    fireEvent.click(button);
    expect(onRetry).not.toHaveBeenCalled();
  });

  it("stays focusable so keyboard users reach the reason, and shows it on focus", () => {
    renderButton({ eligibility: BLOCKED });
    const button = screen.getByRole("button", { name: "Retry reply" });
    expect(screen.getByTestId("retry-reason")).toHaveClass("sr-only");
    button.focus();
    fireEvent.focus(button);
    expect(button).toHaveFocus();
    expect(screen.getByTestId("retry-reason")).not.toHaveClass("sr-only");
  });

  it("reveals the reason on tap of the disabled control", () => {
    renderButton({ eligibility: BLOCKED });
    fireEvent.click(screen.getByRole("button", { name: "Retry reply" }));
    expect(screen.getByTestId("retry-reason")).not.toHaveClass("sr-only");
  });

  it("is disabled with a client-side reason when disconnected", () => {
    renderButton({ connected: false });
    expect(screen.getByRole("button", { name: "Retry reply" })).toHaveAccessibleDescription(
      /reconnecting/i,
    );
  });

  it("is disabled while a turn or retry is running", () => {
    const onRetry = renderButton({ busy: true });
    fireEvent.click(screen.getByRole("button", { name: "Retry reply" }));
    expect(onRetry).not.toHaveBeenCalled();
  });

  it("is unavailable on older replies", () => {
    renderButton({ isLatest: false });
    expect(screen.getByRole("button", { name: "Retry reply" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("hides entirely for a turn pending confirmation", () => {
    renderButton({
      eligibility: { available: false, reason_code: "turn_pending", reason_text: "Waiting" },
    });
    expect(screen.queryByRole("button", { name: "Retry reply" })).not.toBeInTheDocument();
  });

  it("renders nothing until eligibility has loaded", () => {
    renderButton({ eligibility: undefined });
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("with an empty plan, one press retries and sends no plan", () => {
    const onRetry = renderButton();
    fireEvent.click(screen.getByRole("button", { name: "Retry reply" }));
    expect(onRetry).toHaveBeenCalledWith();
    expect(screen.queryByRole("group")).not.toBeInTheDocument();
  });

  describe("with a plan", () => {
    it("opens a named group listing each effect and its undo note, and does not send", () => {
      const onRetry = renderButton({ eligibility: WITH_PLAN });
      fireEvent.click(screen.getByRole("button", { name: "Retry reply" }));
      const group = screen.getByRole("group", { name: /undo what this reply did/i });
      expect(within(group).getByText("set a reminder")).toBeInTheDocument();
      expect(
        within(group).getByText("Does not recall a notification already shown"),
      ).toBeInTheDocument();
      expect(onRetry).not.toHaveBeenCalled();
    });

    it("moves focus to Continue on open", () => {
      renderButton({ eligibility: WITH_PLAN });
      fireEvent.click(screen.getByRole("button", { name: "Retry reply" }));
      expect(screen.getByRole("button", { name: "Continue" })).toHaveFocus();
    });

    it("Continue sends the confirmed entry ids and closes", () => {
      const onRetry = renderButton({ eligibility: WITH_PLAN });
      fireEvent.click(screen.getByRole("button", { name: "Retry reply" }));
      fireEvent.click(screen.getByRole("button", { name: "Continue" }));
      expect(onRetry).toHaveBeenCalledWith(["e1"]);
      expect(screen.queryByRole("group")).not.toBeInTheDocument();
    });

    it("Cancel closes without sending and returns focus to Retry", () => {
      const onRetry = renderButton({ eligibility: WITH_PLAN });
      const retry = screen.getByRole("button", { name: "Retry reply" });
      fireEvent.click(retry);
      fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
      expect(onRetry).not.toHaveBeenCalled();
      expect(screen.queryByRole("group")).not.toBeInTheDocument();
      expect(retry).toHaveFocus();
    });

    it("Escape closes without sending and returns focus to Retry", () => {
      const onRetry = renderButton({ eligibility: WITH_PLAN });
      const retry = screen.getByRole("button", { name: "Retry reply" });
      fireEvent.click(retry);
      fireEvent.keyDown(screen.getByRole("button", { name: "Continue" }), { key: "Escape" });
      expect(onRetry).not.toHaveBeenCalled();
      expect(screen.queryByRole("group")).not.toBeInTheDocument();
      expect(retry).toHaveFocus();
    });

    it("never opens when the control is disabled", () => {
      renderButton({ eligibility: WITH_PLAN, busy: true });
      fireEvent.click(screen.getByRole("button", { name: "Retry reply" }));
      expect(screen.queryByRole("group")).not.toBeInTheDocument();
    });
  });
});
