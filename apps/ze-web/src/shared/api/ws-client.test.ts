import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import { send } from "./ws-client";

describe("send", () => {
  it("returns false when socket is not open", () => {
    expect(send({ type: "ping" })).toBe(false);
  });
});

class FakeSocket {
  static OPEN = 1;
  static instances: FakeSocket[] = [];
  readyState = 1;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  constructor(public url: string) {
    FakeSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.readyState = 3;
    this.onclose?.();
  }
}

async function loadClient() {
  vi.resetModules();
  vi.doMock("@/shared/config", () => ({
    getConfig: () => ({ serverUrl: "http://ze.test", apiKey: "k" }),
  }));
  return import("./ws-client");
}

describe("connection lifecycle", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("clears every thread's thinking state when the socket closes", async () => {
    const { startWs, useWsStore } = await loadClient();
    startWs();
    const socket = FakeSocket.instances[0];
    socket.onopen?.();
    useWsStore.getState().setThreadThinking("t1", true);
    useWsStore.getState().setThreadTypingText("t1", "Searching…");

    socket.onclose?.();

    expect(useWsStore.getState().thinkingThreads).toEqual({});
    expect(useWsStore.getState().typingTextThreads).toEqual({});
    expect(useWsStore.getState().isConnected).toBe(false);
  });

  it("keeps in-flight thinking state when a new connection opens", async () => {
    const { startWs, useWsStore } = await loadClient();
    startWs();
    const socket = FakeSocket.instances[0];
    socket.onopen?.();
    useWsStore.getState().setThreadThinking("t1", true);

    socket.onopen?.();

    expect(useWsStore.getState().thinkingThreads).toEqual({ t1: true });
    expect(useWsStore.getState().isConnected).toBe(true);
  });

  it("drops a half-open socket after two silent ping intervals", async () => {
    const { startWs, useWsStore } = await loadClient();
    startWs();
    const socket = FakeSocket.instances[0];
    socket.onopen?.();
    useWsStore.getState().setThreadThinking("t1", true);

    vi.advanceTimersByTime(30_000);
    expect(socket.sent).toHaveLength(1);
    vi.advanceTimersByTime(30_000);
    expect(socket.sent).toHaveLength(2);
    vi.advanceTimersByTime(30_000);

    expect(useWsStore.getState().isConnected).toBe(false);
    expect(useWsStore.getState().thinkingThreads).toEqual({});
    vi.advanceTimersByTime(1_000);
    expect(FakeSocket.instances).toHaveLength(2);
  });

  it("keeps the connection while frames keep arriving", async () => {
    const { startWs, useWsStore } = await loadClient();
    startWs();
    const socket = FakeSocket.instances[0];
    socket.onopen?.();

    for (let i = 0; i < 6; i++) {
      vi.advanceTimersByTime(30_000);
      socket.onmessage?.({ data: JSON.stringify({ type: "pong" }) });
    }

    expect(useWsStore.getState().isConnected).toBe(true);
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it("ignores the close of a socket that reconnect() already replaced", async () => {
    const { startWs, reconnect, useWsStore } = await loadClient();
    startWs();
    const first = FakeSocket.instances[0];
    first.onopen?.();

    reconnect();
    const second = FakeSocket.instances[1];
    second.onopen?.();

    expect(useWsStore.getState().isConnected).toBe(true);
    expect(FakeSocket.instances).toHaveLength(2);
  });
});
