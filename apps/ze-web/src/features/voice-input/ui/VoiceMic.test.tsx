import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useVoiceInput } from "../model/store";
import { VoiceMic } from "./VoiceMic";

const start = vi.fn();
const stop = vi.fn();
const dismiss = vi.fn();
const base = { status: "idle" as const, startedAt: null, reason: null, failure: null, notice: null, pending: null, start, stop, dismiss, retry: vi.fn() };

beforeEach(() => {
  vi.useFakeTimers();
  start.mockClear();
  stop.mockClear();
  dismiss.mockClear();
  useVoiceInput.setState(base);
});
afterEach(() => vi.useRealTimers());

describe("VoiceMic", () => {
  it("idle: a 44 px mic that starts recording", () => {
    render(<VoiceMic blocked={null} />);
    const mic = screen.getByRole("button", { name: "Speak to Ze (hold V)" });
    expect(mic).toHaveClass("ctl");
    fireEvent.click(mic);
    expect(start).toHaveBeenCalledTimes(1);
  });

  it("recording: pressed, stop label, elapsed time, press stops", () => {
    useVoiceInput.setState({ status: "recording", startedAt: performance.now() });
    render(<VoiceMic blocked={null} />);
    act(() => void vi.advanceTimersByTime(12_000));
    const mic = screen.getByRole("button", { name: "Stop recording" });
    expect(mic).toHaveAttribute("aria-pressed", "true");
    expect(mic).toHaveTextContent("0:12");
    fireEvent.click(mic);
    expect(stop).toHaveBeenCalledTimes(1);
  });

  it("shows the seconds left from 105 s", () => {
    useVoiceInput.setState({ status: "recording", startedAt: performance.now() });
    render(<VoiceMic blocked={null} />);
    act(() => void vi.advanceTimersByTime(104_000));
    expect(screen.getByRole("button", { name: "Stop recording" })).toHaveTextContent("1:44");
    act(() => void vi.advanceTimersByTime(1_000));
    expect(screen.getByRole("button", { name: "Stop recording" })).toHaveTextContent("10s left");
  });

  it("recording before the microphone is ready shows 0:00", () => {
    useVoiceInput.setState({ status: "recording", startedAt: null });
    render(<VoiceMic blocked={null} />);
    expect(screen.getByRole("button", { name: "Stop recording" })).toHaveTextContent("0:00");
  });

  it("transcribing: disabled and busy", () => {
    useVoiceInput.setState({ status: "transcribing" });
    render(<VoiceMic blocked={null} />);
    const mic = screen.getByRole("button", { name: "Transcribing" });
    expect(mic).toBeDisabled();
    expect(mic).toHaveAttribute("aria-busy", "true");
  });

  it("blocked: disabled with the reason as label and title", () => {
    render(<VoiceMic blocked="Ze is offline" />);
    const mic = screen.getByRole("button", { name: "Ze is offline" });
    expect(mic).toBeDisabled();
    expect(mic).toHaveAttribute("title", "Ze is offline");
  });

  it("unavailable: disabled with the reason", () => {
    useVoiceInput.setState({ status: "unavailable", reason: "No microphone found." });
    render(<VoiceMic blocked={null} />);
    const mic = screen.getByRole("button", { name: "No microphone found." });
    expect(mic).toBeDisabled();
    expect(mic).toHaveAttribute("title", "No microphone found.");
  });

  it("after a failure a press dismisses it and records again", () => {
    useVoiceInput.setState({ status: "failed", failure: { kind: "retryable", detail: "x" } });
    render(<VoiceMic blocked={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Speak to Ze (hold V)" }));
    expect(dismiss).toHaveBeenCalledTimes(1);
    expect(start).toHaveBeenCalledTimes(1);
  });
});
