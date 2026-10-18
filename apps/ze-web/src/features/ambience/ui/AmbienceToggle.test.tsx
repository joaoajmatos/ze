import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mockMatchMedia } from "@/test/match-media";
import { AmbienceToggle } from "./AmbienceToggle";

class QuietAudioContext {
  currentTime = 0;
  destination = {};
  resume = () => Promise.resolve();
  close = () => Promise.resolve();
  createGain = () => ({ gain: { value: 0, setTargetAtTime: () => {} }, connect: (n: unknown) => n, disconnect: () => {} });
  createOscillator = () => ({ type: "sine", frequency: { value: 0 }, detune: {}, connect: (n: unknown) => n, start: () => {}, stop: () => {} });
  createBiquadFilter = () => ({ type: "lowpass", frequency: { value: 0 }, connect: (n: unknown) => n });
}

let mm: ReturnType<typeof mockMatchMedia>;
beforeEach(() => {
  localStorage.clear();
  window.AudioContext = QuietAudioContext as unknown as typeof AudioContext;
  mm = mockMatchMedia({});
});
afterEach(() => {
  mm.restore();
  vi.restoreAllMocks();
});

describe("AmbienceToggle", () => {
  it("is a 44 px control, off by default, named for its state", () => {
    render(<AmbienceToggle />);
    const button = screen.getByRole("button", { name: "Ambience off" });
    expect(button).toHaveClass("ctl");
    expect(button).toHaveAttribute("aria-pressed", "false");
  });

  it("flips aria-pressed, label and icon when pressed", () => {
    const { container } = render(<AmbienceToggle />);
    expect(container.querySelector("svg")).toHaveClass("lucide-volume-x");
    fireEvent.click(screen.getByRole("button", { name: "Ambience off" }));
    const button = screen.getByRole("button", { name: "Ambience on" });
    expect(button).toHaveAttribute("aria-pressed", "true");
    expect(container.querySelector("svg")).toHaveClass("lucide-volume2");
  });
});
