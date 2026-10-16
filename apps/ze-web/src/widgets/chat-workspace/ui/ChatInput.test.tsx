import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChatInput } from "./ChatInput";

describe("ChatInput", () => {
  it("shows the static AI disclosure under the composer", () => {
    render(<ChatInput value="" onChange={vi.fn()} onSend={vi.fn()} />);
    expect(screen.getByText("Ze is AI and can make mistakes.")).toBeInTheDocument();
  });

  it("keeps the disclosure while the composer is disabled", () => {
    render(<ChatInput value="" onChange={vi.fn()} onSend={vi.fn()} disabled />);
    expect(screen.getByText("Ze is AI and can make mistakes.")).toBeInTheDocument();
  });
});
