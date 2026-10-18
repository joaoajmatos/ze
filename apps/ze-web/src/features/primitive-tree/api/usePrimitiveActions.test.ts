import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({
  navigate: vi.fn(),
  send: vi.fn((_frame: unknown) => true),
  sendTurn: vi.fn(() => true),
  showNotice: vi.fn(),
  handlers: [] as ((f: { id: string; ok: boolean; line: string }) => void)[],
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
  useFrame: (_type: string, handler: (f: { id: string; ok: boolean; line: string }) => void) => {
    m.handlers.length = 0;
    m.handlers.push(handler);
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
});
