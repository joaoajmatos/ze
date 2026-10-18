import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({
  navigate: vi.fn(),
  send: vi.fn((_frame: unknown) => true),
  sendTurn: vi.fn(() => true),
  showNotice: vi.fn(),
  handlers: [] as ((f: { id: string; ok: boolean; line: string }) => void)[],
  cancelHandlers: [] as ((f: { id: string; reason?: string }) => void)[],
  connected: true,
}));

vi.mock("react-router-dom", () => ({ useNavigate: () => m.navigate }));
vi.mock("@/entities/onboarding-session", () => ({
  useOnboardingSession: (s: (x: { sessionId: string | null; completed: boolean }) => unknown) =>
    s({ sessionId: null, completed: true }),
}));
vi.mock("@/entities/session", () => ({
  useSession: (s: (x: { threadId: string }) => unknown) => s({ threadId: "t-1" }),
}));
vi.mock("@/shared/api", () => ({
  send: m.send,
  useWsStore: (s: (x: { isConnected: boolean }) => unknown) => s({ isConnected: m.connected }),
  useFrame: (type: string, handler: (f: never) => void) => {
    const list = type === "confirm_cancel" ? m.cancelHandlers : m.handlers;
    list.length = 0;
    list.push(handler as never);
  },
}));
vi.mock("@/shared/lib", () => ({
  useSendNotice: (s: (x: { showNotice: typeof m.showNotice }) => unknown) => s({ showNotice: m.showNotice }),
}));

import { createElement, type ReactNode } from "react";
import { TurnSenderProvider } from "../model/turn-sender";
import { usePrimitiveActions } from "./usePrimitiveActions";

const toolAction = { kind: "tool", owner: "news", tool: "mark_source_read", args: { source_id: "s-12" } } as const;

function setup() {
  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(TurnSenderProvider, { sendTurn: m.sendTurn, children });
  return renderHook(() => usePrimitiveActions(), { wrapper }).result.current;
}

describe("usePrimitiveActions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    m.connected = true;
    m.send.mockReturnValue(true);
    m.sendTurn.mockReturnValue(true);
  });
  afterEach(() => vi.useRealTimers());

  it("navigate to a section of a place navigates there", () => {
    void setup().onAction?.({ kind: "navigate", route: "/governance#connections" });
    expect(m.navigate).toHaveBeenCalledWith("/governance#connections");
  });

  it("navigate to a nested place route navigates", () => {
    void setup().onAction?.({ kind: "navigate", route: "/mind/x" });
    expect(m.navigate).toHaveBeenCalledWith("/mind/x");
  });

  it.each(["mind/x", "/nowhere/else", "//evil.example"])("navigate to %s shows a notice", (route) => {
    void setup().onAction?.({ kind: "navigate", route });
    expect(m.navigate).not.toHaveBeenCalled();
    expect(m.showNotice).toHaveBeenCalledWith("That link can't be opened.");
  });

  it("ask sends a turn on the selected thread", () => {
    void setup().onAction?.({ kind: "ask", text: "What's new?" });
    expect(m.sendTurn).toHaveBeenCalledWith("t-1", "What's new?");
  });

  it("compose sends with the preset origin and its compose", () => {
    void setup().onAction?.({ kind: "compose", compose: "slipping" });
    expect(m.sendTurn).toHaveBeenCalledWith("t-1", "What's slipping?", {
      explicitContext: expect.objectContaining({ origin: "preset", compose: "slipping" }),
    });
  });

  it("tool sends one ui_action frame and resolves true on the matching result, showing its line", async () => {
    const actions = setup();
    const pending = actions.onAction?.(toolAction) as Promise<boolean>;
    const frame = m.send.mock.calls[0][0] as { type: string; id: string; thread_id: string; action: unknown };
    expect(frame).toMatchObject({ type: "ui_action", thread_id: "t-1", action: toolAction });
    expect(frame.id).toBeTruthy();
    act(() => m.handlers[0]({ id: "other", ok: false, line: "no" }));
    act(() => m.handlers[0]({ id: frame.id, ok: true, line: "Marked as read." }));
    await expect(pending).resolves.toBe(true);
    expect(m.showNotice).toHaveBeenCalledWith("Marked as read.");
  });

  it("tool resolves false when the result is not ok", async () => {
    const pending = setup().onAction?.(toolAction) as Promise<boolean>;
    const id = (m.send.mock.calls[0][0] as { id: string }).id;
    act(() => m.handlers[0]({ id, ok: false, line: "Couldn't mark it read." }));
    await expect(pending).resolves.toBe(false);
    expect(m.showNotice).toHaveBeenCalledWith("Couldn't mark it read.");
  });

  it("tool resolves false while disconnected", async () => {
    m.send.mockReturnValue(false);
    await expect(setup().onAction?.(toolAction)).resolves.toBe(false);
    expect(m.showNotice).toHaveBeenCalledWith("Not connected. Retry when Ze reconnects.");
  });

  it("ignores a second tool press while one is pending", async () => {
    const actions = setup();
    const first = actions.onAction?.(toolAction) as Promise<boolean>;
    await expect(actions.onAction?.(toolAction)).resolves.toBe(false);
    expect(m.send).toHaveBeenCalledTimes(1);
    const id = (m.send.mock.calls[0][0] as { id: string }).id;
    act(() => m.handlers[0]({ id, ok: true, line: "Done." }));
    await first;
    void actions.onAction?.(toolAction);
    expect(m.send).toHaveBeenCalledTimes(2);
  });

  it("gives up after the confirmation timeout", async () => {
    vi.useFakeTimers();
    const pending = setup().onAction?.(toolAction) as Promise<boolean>;
    await vi.advanceTimersByTimeAsync(16 * 60_000);
    await expect(pending).resolves.toBe(false);
  });

  it("settles false when the socket drops while a press is pending", async () => {
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(TurnSenderProvider, { sendTurn: m.sendTurn, children });
    const hook = renderHook(() => usePrimitiveActions(), { wrapper });
    const pending = hook.result.current.onAction?.(toolAction) as Promise<boolean>;
    m.connected = false;
    hook.rerender();
    await expect(pending).resolves.toBe(false);
    m.connected = true;
    hook.rerender();
    void hook.result.current.onAction?.(toolAction);
    expect(m.send).toHaveBeenCalledTimes(2);
  });

  it("settles false when the server cancels its gate, but not when it was answered", async () => {
    const actions = setup();
    const answered = actions.onAction?.(toolAction) as Promise<boolean>;
    const id = (m.send.mock.calls[0][0] as { id: string }).id;
    act(() => m.cancelHandlers[0]({ id, reason: "answered" }));
    act(() => m.handlers[0]({ id, ok: true, line: "Done." }));
    await expect(answered).resolves.toBe(true);
    const cancelled = actions.onAction?.(toolAction) as Promise<boolean>;
    const id2 = (m.send.mock.calls[1][0] as { id: string }).id;
    act(() => m.cancelHandlers[0]({ id: id2 }));
    await expect(cancelled).resolves.toBe(false);
  });

  it("a busy refusal leaves the next press possible", async () => {
    const actions = setup();
    const first = actions.onAction?.(toolAction) as Promise<boolean>;
    const id = (m.send.mock.calls[0][0] as { id: string }).id;
    act(() => m.handlers[0]({ id, ok: false, line: "Ze is busy. Try again." }));
    await expect(first).resolves.toBe(false);
    void actions.onAction?.(toolAction);
    expect(m.send).toHaveBeenCalledTimes(2);
  });
});
