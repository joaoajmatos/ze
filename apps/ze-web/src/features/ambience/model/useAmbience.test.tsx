import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { presenceActions, usePresenceStore } from "@/entities/presence";
import { mockMatchMedia } from "@/test/match-media";
import { useAmbience } from "./useAmbience";

interface FakeGain {
  gain: { value: number; setTargetAtTime: ReturnType<typeof vi.fn> };
  connect: (n: unknown) => unknown;
  disconnect: () => void;
}

const made = vi.hoisted(() => ({ contexts: [] as unknown[] }));

class FakeAudioContext {
  currentTime = 0;
  destination = {};
  gains: FakeGain[] = [];
  oscillators = 0;
  resume = vi.fn(() => Promise.resolve());
  close = vi.fn(() => Promise.resolve());
  constructor() {
    made.contexts.push(this);
  }
  createGain(): FakeGain {
    const g: FakeGain = { gain: { value: 1, setTargetAtTime: vi.fn() }, connect: (n) => n, disconnect: () => {} };
    this.gains.push(g);
    return g;
  }
  createOscillator() {
    this.oscillators += 1;
    return { type: "sine", frequency: { value: 0 }, detune: {}, connect: (n: unknown) => n, start: vi.fn(), stop: vi.fn() };
  }
  createBiquadFilter() {
    return { type: "lowpass", frequency: { value: 0 }, connect: (n: unknown) => n };
  }
}

const contexts = () => made.contexts as FakeAudioContext[];
const master = () => contexts()[0].gains[0];
const lastTarget = () => master().gain.setTargetAtTime.mock.calls.at(-1)?.[0];

let mm: ReturnType<typeof mockMatchMedia>;

beforeEach(() => {
  made.contexts.length = 0;
  vi.stubGlobal("AudioContext", FakeAudioContext);
  window.AudioContext = FakeAudioContext as unknown as typeof AudioContext;
  localStorage.clear();
  usePresenceStore.getState().reset();
  mm = mockMatchMedia({});
});
afterEach(() => {
  mm.restore();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("useAmbience", () => {
  it("starts off with no audio context on a fresh browser", () => {
    const { result } = renderHook(() => useAmbience());
    expect(result.current.on).toBe(false);
    expect(contexts()).toHaveLength(0);
  });

  it("toggling on creates the context, resumes it and remembers on", () => {
    const { result } = renderHook(() => useAmbience());
    act(() => result.current.toggle());
    expect(result.current.on).toBe(true);
    expect(contexts()).toHaveLength(1);
    expect(contexts()[0].resume).toHaveBeenCalled();
    expect(localStorage.getItem("ze.ambience")).toBe("on");
  });

  it("toggling off fades the master to 0 and remembers off", () => {
    const { result } = renderHook(() => useAmbience());
    act(() => result.current.toggle());
    act(() => result.current.toggle());
    expect(result.current.on).toBe(false);
    expect(lastTarget()).toBe(0);
    expect(localStorage.getItem("ze.ambience")).toBe("off");
  });

  it("a remembered on reads on but starts only at the first pointerdown", () => {
    localStorage.setItem("ze.ambience", "on");
    const { result } = renderHook(() => useAmbience());
    expect(result.current.on).toBe(true);
    expect(contexts()).toHaveLength(0);
    act(() => void window.dispatchEvent(new Event("pointerdown")));
    expect(contexts()).toHaveLength(1);
  });

  it("a remembered on also starts at the first keydown", () => {
    localStorage.setItem("ze.ambience", "on");
    renderHook(() => useAmbience());
    act(() => void window.dispatchEvent(new Event("keydown")));
    expect(contexts()).toHaveLength(1);
  });

  it("under reduced motion a remembered on waits for the toggle", () => {
    mm.set("(prefers-reduced-motion: reduce)", true);
    localStorage.setItem("ze.ambience", "on");
    const { result } = renderHook(() => useAmbience());
    expect(result.current.on).toBe(false);
    act(() => void window.dispatchEvent(new Event("pointerdown")));
    expect(contexts()).toHaveLength(0);
    act(() => result.current.toggle());
    expect(result.current.on).toBe(true);
    expect(contexts()).toHaveLength(1);
  });

  it("survives localStorage that throws on read and write", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const { result } = renderHook(() => useAmbience());
    expect(result.current.on).toBe(false);
    expect(() => act(() => result.current.toggle())).not.toThrow();
    expect(result.current.on).toBe(true);
  });

  it("ducks to silence while recording and returns after", () => {
    const { result } = renderHook(() => useAmbience());
    act(() => result.current.toggle());
    act(() => presenceActions.voice("recording"));
    expect(lastTarget()).toBe(0);
    act(() => presenceActions.voice("none"));
    expect(lastTarget()).toBe(0.16);
  });
});
