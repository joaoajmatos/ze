import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useVoiceInput } from "./store";
import { useHoldToTalk } from "./useHoldToTalk";

const start = vi.fn();
const stop = vi.fn();
const dismiss = vi.fn();
let status: "idle" | "recording";

function key(type: "keydown" | "keyup", init: KeyboardEventInit = {}, target: EventTarget = window) {
  target.dispatchEvent(new KeyboardEvent(type, { key: "v", bubbles: true, ...init }));
}

beforeEach(() => {
  vi.useFakeTimers();
  [start, stop, dismiss].forEach((f) => f.mockClear());
  status = "idle";
  start.mockImplementation(() => {
    status = "recording";
    useVoiceInput.setState({ status });
  });
  useVoiceInput.setState({ status: "idle", start, stop, dismiss, retry: vi.fn() });
});
afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
});

describe("useHoldToTalk", () => {
  it("v down starts, a long hold's v up stops", () => {
    renderHook(() => useHoldToTalk(true));
    key("keydown");
    expect(start).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(800);
    key("keyup");
    expect(stop).toHaveBeenCalledTimes(1);
    expect(dismiss).not.toHaveBeenCalled();
  });

  it("accepts a capital V", () => {
    renderHook(() => useHoldToTalk(true));
    key("keydown", { key: "V" });
    expect(start).toHaveBeenCalledTimes(1);
  });

  it("a release within 300 ms discards", () => {
    renderHook(() => useHoldToTalk(true));
    key("keydown");
    vi.advanceTimersByTime(200);
    key("keyup");
    expect(dismiss).toHaveBeenCalledTimes(1);
    expect(stop).not.toHaveBeenCalled();
  });

  it.each([
    ["a modifier", { ctrlKey: true }],
    ["a repeat", { repeat: true }],
  ])("ignores %s", (_n, init) => {
    renderHook(() => useHoldToTalk(true));
    key("keydown", init);
    expect(start).not.toHaveBeenCalled();
  });

  it.each(["input", "textarea", "div"])("ignores a keydown in a %s text field", (tag) => {
    renderHook(() => useHoldToTalk(true));
    const el = document.createElement(tag);
    if (tag === "div") {
      el.setAttribute("contenteditable", "true");
      Object.defineProperty(el, "isContentEditable", { value: true });
    }
    document.body.append(el);
    key("keydown", {}, el);
    expect(start).not.toHaveBeenCalled();
  });

  it("ignores a keydown while a dialog is open", () => {
    renderHook(() => useHoldToTalk(true));
    const d = document.createElement("div");
    d.setAttribute("role", "dialog");
    document.body.append(d);
    key("keydown");
    expect(start).not.toHaveBeenCalled();
  });

  it("does nothing when disabled or when not idle", () => {
    const { rerender } = renderHook(({ on }) => useHoldToTalk(on), { initialProps: { on: false } });
    key("keydown");
    expect(start).not.toHaveBeenCalled();
    useVoiceInput.setState({ status: "transcribing" });
    rerender({ on: true });
    key("keydown");
    expect(start).not.toHaveBeenCalled();
  });

  it("a keyup that did not begin a hold does nothing", () => {
    renderHook(() => useHoldToTalk(true));
    key("keyup");
    expect(stop).not.toHaveBeenCalled();
    expect(dismiss).not.toHaveBeenCalled();
  });

  it("stops when the window blurs during a hold", () => {
    renderHook(() => useHoldToTalk(true));
    key("keydown");
    vi.advanceTimersByTime(800);
    window.dispatchEvent(new Event("blur"));
    expect(stop).toHaveBeenCalledTimes(1);
    key("keyup");
    expect(stop).toHaveBeenCalledTimes(1);
  });

  it("turning off mid-hold discards the recording instead of uploading it", () => {
    const { rerender } = renderHook(({ on }) => useHoldToTalk(on), { initialProps: { on: true } });
    key("keydown");
    vi.advanceTimersByTime(800);
    rerender({ on: false });
    expect(dismiss).toHaveBeenCalledTimes(1);
    expect(stop).not.toHaveBeenCalled();
  });
});
