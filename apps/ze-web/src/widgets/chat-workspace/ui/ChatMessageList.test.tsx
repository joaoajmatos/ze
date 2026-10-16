import type { MessageSchema } from "@myguyze/ze-client";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { useSession } from "@/entities/session";
import { ChatMessageList } from "./ChatMessageList";

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

const base = { messages: [], showTyping: false };

describe("ChatMessageList delivery failure", () => {
  it("shows a retry row when delivery failed and calls onRetry", () => {
    const onRetry = vi.fn();
    render(<ChatMessageList {...base} deliveryFailed onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/something went wrong/i);
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("shows no retry row by default", () => {
    render(<ChatMessageList {...base} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("hides the retry row while a new turn is typing", () => {
    render(<ChatMessageList {...base} showTyping deliveryFailed onRetry={vi.fn()} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("ChatMessageList highlighted message", () => {
  const message: MessageSchema = {
    id: "m-1",
    role: "assistant",
    text: "hello",
    components: [],
    read: true,
    created_at: "2026-10-16T10:00:00Z",
    thread_id: "t-1",
  };

  afterEach(() => useSession.getState().setHighlightMessage(null));

  it("says the originating message is gone when the highlighted id is not in the thread", () => {
    useSession.getState().setHighlightMessage("missing");
    render(<ChatMessageList messages={[message]} showTyping={false} />);
    expect(screen.getByText(/no longer available/i)).toBeInTheDocument();
  });

  it("stays quiet when the highlighted message is present", () => {
    useSession.getState().setHighlightMessage("m-1");
    render(<ChatMessageList messages={[message]} showTyping={false} />);
    expect(screen.queryByText(/no longer available/i)).not.toBeInTheDocument();
  });

  it("stays quiet while the thread is still loading", () => {
    useSession.getState().setHighlightMessage("m-1");
    render(<ChatMessageList messages={[]} showTyping={false} />);
    expect(screen.queryByText(/no longer available/i)).not.toBeInTheDocument();
  });
});
