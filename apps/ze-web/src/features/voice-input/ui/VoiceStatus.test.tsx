import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useVoiceInput } from "../model/store";
import { VoiceStatus } from "./VoiceStatus";

const start = vi.fn();
const retry = vi.fn();
const dismiss = vi.fn();
const base = { status: "idle" as const, startedAt: null, reason: null, failure: null, notice: null, pending: null, start, stop: vi.fn(), retry, dismiss };

beforeEach(() => {
  [start, retry, dismiss].forEach((f) => f.mockClear());
  useVoiceInput.setState(base);
});

describe("VoiceStatus", () => {
  it("is an empty polite live region when idle", () => {
    render(<VoiceStatus />);
    const line = screen.getByRole("status");
    expect(line).toHaveAttribute("aria-live", "polite");
    expect(line).toBeEmptyDOMElement();
  });

  it("says Transcribing…", () => {
    useVoiceInput.setState({ status: "transcribing" });
    render(<VoiceStatus />);
    expect(screen.getByRole("status")).toHaveTextContent("Transcribing…");
  });

  it("a retryable failure shows its line with Retry and Dismiss", () => {
    useVoiceInput.setState({ status: "failed", failure: { kind: "retryable", detail: "I couldn't make out the recording." } });
    render(<VoiceStatus />);
    expect(screen.getByRole("status")).toHaveTextContent("I couldn't make out the recording.");
    const retryBtn = screen.getByRole("button", { name: "Retry" });
    const dismissBtn = screen.getByRole("button", { name: "Dismiss" });
    expect(retryBtn.className).toMatch(/min-h-11/);
    expect(dismissBtn.className).toMatch(/min-h-11/);
    fireEvent.click(retryBtn);
    expect(retry).toHaveBeenCalledTimes(1);
    fireEvent.click(dismissBtn);
    expect(dismiss).toHaveBeenCalledTimes(1);
  });

  it("a rerecord failure offers Record again and no Retry", () => {
    useVoiceInput.setState({ status: "failed", failure: { kind: "rerecord", detail: "That recording is too long: the limit is 2 minutes." } });
    render(<VoiceStatus />);
    expect(screen.getByRole("status")).toHaveTextContent("too long");
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    const order: string[] = [];
    dismiss.mockImplementationOnce(() => order.push("dismiss"));
    start.mockImplementationOnce(() => order.push("start"));
    fireEvent.click(screen.getByRole("button", { name: "Record again" }));
    expect(order).toEqual(["dismiss", "start"]);
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(dismiss).toHaveBeenCalledTimes(2);
  });

  it("says when Ze heard nothing", () => {
    useVoiceInput.setState({ notice: "heard_nothing" });
    render(<VoiceStatus />);
    expect(screen.getByRole("status")).toHaveTextContent("Ze heard nothing");
  });
});
