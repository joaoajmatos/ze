import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import type { MessageFeedback } from "@/entities/message-feedback";
import { useSession } from "@/entities/session";
import { FeedbackSection } from "./FeedbackSection";

function view(overrides: Partial<MessageFeedback> = {}): MessageFeedback {
  return {
    message_id: "m1",
    current: null,
    history: [],
    retry: { available: true, reason_code: null, reason_text: null },
    replaces: null,
    replaced_by: null,
    trace_present: true,
    ...overrides,
  };
}

describe("FeedbackSection", () => {
  beforeEach(() => useSession.getState().setHighlightMessage(null));

  it("renders nothing until feedback state exists", () => {
    const { container } = render(<FeedbackSection feedback={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("says 'No feedback yet' and invents no value", () => {
    render(<FeedbackSection feedback={view()} />);
    expect(screen.getByText("No feedback yet")).toBeInTheDocument();
    expect(screen.queryByTestId("feedback-current")).not.toBeInTheDocument();
  });

  it("shows the current rating and each change with its time", () => {
    render(
      <FeedbackSection
        feedback={view({
          current: "down",
          history: [
            { kind: "thumbs_up", occurred_at: "2026-10-09T10:00:00Z" },
            { kind: "thumbs_down", occurred_at: "2026-10-09T10:05:00Z" },
          ],
        })}
      />,
    );
    expect(screen.getByTestId("feedback-current")).toHaveTextContent("Thumbs down");
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("Thumbs up");
  });

  it("links a retried reply to its replacement", () => {
    render(
      <FeedbackSection
        feedback={view({
          history: [{ kind: "retry_requested", occurred_at: "2026-10-09T10:00:00Z" }],
          replaced_by: "m2",
        })}
      />,
    );
    expect(screen.getByText(/retried/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /view replacement/i }));
    expect(useSession.getState().highlightMessageId).toBe("m2");
  });

  it("marks a replacement as replacing an earlier reply", () => {
    render(<FeedbackSection feedback={view({ replaces: "m0" })} />);
    expect(screen.getByText("Replaces an earlier reply")).toBeInTheDocument();
  });

  it("marks messages without a trace", () => {
    render(<FeedbackSection feedback={view({ current: "up", trace_present: false })} />);
    expect(screen.getByText("No trace recorded")).toBeInTheDocument();
  });
});
