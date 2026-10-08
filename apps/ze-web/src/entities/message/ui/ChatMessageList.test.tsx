import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
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
