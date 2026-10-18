import type { WsInboundFrame as InboundFrame, WsOutboundFrame as OutboundFrame } from "@myguyze/ze-client";
import { useEffect, useRef } from "react";
import { create } from "zustand";
import { getConfig } from "@/shared/config";

interface WsStore {
  isConnected: boolean;
  /** Another window took over the connection (close 4000); this one waits for focus. */
  displaced: boolean;
  thinkingThreads: Record<string, boolean>;
  typingTextThreads: Record<string, string | null>;
  attentionThreads: Record<string, boolean>;
  /** Threads whose turn was in flight when the socket dropped; consumed on reconnect. */
  interruptedThreads: Record<string, boolean>;
  setConnected: (v: boolean) => void;
  setThreadThinking: (threadId: string, v: boolean) => void;
  setThreadTypingText: (threadId: string, text: string | null) => void;
  setThreadAttention: (threadId: string, v: boolean) => void;
  clearThreadInterrupted: (threadId: string) => void;
}

export const useWsStore = create<WsStore>((set) => ({
  isConnected: false,
  displaced: false,
  thinkingThreads: {},
  typingTextThreads: {},
  attentionThreads: {},
  interruptedThreads: {},
  setConnected: (v) => set({ isConnected: v }),
  setThreadThinking: (threadId, v) =>
    set((s) => ({ thinkingThreads: { ...s.thinkingThreads, [threadId]: v } })),
  setThreadTypingText: (threadId, text) =>
    set((s) => ({ typingTextThreads: { ...s.typingTextThreads, [threadId]: text } })),
  setThreadAttention: (threadId, v) =>
    set((s) => ({ attentionThreads: { ...s.attentionThreads, [threadId]: v } })),
  clearThreadInterrupted: (threadId) =>
    set((s) => {
      const rest = { ...s.interruptedThreads };
      delete rest[threadId];
      return { interruptedThreads: rest };
    }),
}));

type FrameType = InboundFrame["type"];
const frameHandlers = new Map<FrameType, Set<(f: InboundFrame) => void>>();

function dispatch(frame: InboundFrame) {
  frameHandlers.get(frame.type)?.forEach((h) => h(frame));
}

let ws: WebSocket | null = null;
let retryTimeout: ReturnType<typeof setTimeout> | null = null;
let retryDelay = 1000;
let pingInterval: ReturnType<typeof setInterval> | null = null;
let lastFrameAt = 0;

const PING_INTERVAL_MS = 30_000;
// A live server answers every ping with a pong, so two silent intervals mean a
// half-open socket the browser has not noticed yet.
const SILENCE_LIMIT_MS = PING_INTERVAL_MS * 2;
// The server closes the older socket with this code when a newer one connects.
// Reconnecting on it would make two windows displace each other forever.
const DISPLACED_CODE = 4000;

function buildUrl() {
  const cfg = getConfig();
  if (!cfg) return null;
  const base = cfg.serverUrl.replace(/^http/, "ws");
  return `${base}/ws?token=${encodeURIComponent(cfg.apiKey)}`;
}

function scheduleReconnect() {
  if (retryTimeout) return;
  retryTimeout = setTimeout(() => {
    retryTimeout = null;
    connect();
  }, retryDelay);
  retryDelay = Math.min(retryDelay * 2, 30_000);
}

function stopPing() {
  if (pingInterval) clearInterval(pingInterval);
  pingInterval = null;
}

function handleClosed(socket: WebSocket, displaced = false) {
  // A replaced socket (reconnect() opens a new one before the old one closes)
  // must not tear down its successor.
  if (ws !== socket) return;
  ws = null;
  stopPing();
  // In-flight turns on this connection are unobservable now. Unlock the composer;
  // the reply is stored server-side and arrives via unread replay or history.
  const inFlight = Object.keys(useWsStore.getState().thinkingThreads).filter(
    (id) => useWsStore.getState().thinkingThreads[id],
  );
  useWsStore.setState((s) => ({
    thinkingThreads: {},
    typingTextThreads: {},
    isConnected: false,
    interruptedThreads: {
      ...s.interruptedThreads,
      ...Object.fromEntries(inFlight.map((id) => [id, true])),
    },
    displaced,
  }));
  if (!displaced) scheduleReconnect();
}

/** Use this window: clear the displaced state and connect now, whatever the document's visibility. */
export function takeOver() {
  if (!useWsStore.getState().displaced || ws || retryTimeout) return;
  useWsStore.setState({ displaced: false });
  retryDelay = 1000;
  connect();
}

function takeOverIfDisplaced() {
  if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
  takeOver();
}

export type ConnectionState = "online" | "displaced" | "offline";

function stateOf(s: { isConnected: boolean; displaced: boolean }): ConnectionState {
  return s.isConnected ? "online" : s.displaced ? "displaced" : "offline";
}

export function connectionState(): ConnectionState {
  return stateOf(useWsStore.getState());
}

/** `displaced` means another window holds the connection; the person can take it back. */
export function useConnectionState(): ConnectionState {
  return useWsStore(stateOf);
}

let focusListening = false;
function listenForFocus() {
  if (focusListening || typeof window === "undefined") return;
  focusListening = true;
  window.addEventListener("focus", takeOverIfDisplaced);
  document.addEventListener("visibilitychange", takeOverIfDisplaced);
}

function connect() {
  const url = buildUrl();
  if (!url) return;

  const socket = new WebSocket(url);
  ws = socket;

  socket.onopen = () => {
    if (ws !== socket) return;
    retryDelay = 1000;
    lastFrameAt = Date.now();
    // Thinking state is deliberately kept: a turn that started before a
    // reconnect may still finish. useChatWorkspace reconciles it from history.
    useWsStore.getState().setConnected(true);
    stopPing();
    pingInterval = setInterval(() => {
      if (Date.now() - lastFrameAt > SILENCE_LIMIT_MS) {
        socket.onclose = null;
        socket.onerror = null;
        socket.onmessage = null;
        try {
          socket.close();
        } catch {
          // already closed
        }
        handleClosed(socket);
        return;
      }
      send({ type: "ping" });
    }, PING_INTERVAL_MS);
  };

  socket.onmessage = (event) => {
    lastFrameAt = Date.now();
    let frame: InboundFrame;
    try {
      frame = JSON.parse(event.data as string) as InboundFrame;
    } catch {
      return;
    }
    dispatch(frame);
  };

  socket.onclose = (event?: CloseEvent) => handleClosed(socket, event?.code === DISPLACED_CODE);

  socket.onerror = () => {
    socket.close();
  };
}

export function send(frame: OutboundFrame): boolean {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(frame));
    return true;
  }
  return false;
}

export function reconnect() {
  if (retryTimeout) {
    clearTimeout(retryTimeout);
    retryTimeout = null;
  }
  ws?.close();
  retryDelay = 1000;
  useWsStore.setState({ displaced: false });
  connect();
}

export function useFrame<T extends FrameType>(
  type: T,
  handler: (f: Extract<InboundFrame, { type: T }>) => void,
) {
  const ref = useRef(handler);
  // Keep handler ref fresh without re-subscribing the frame listener.
  // eslint-disable-next-line react-hooks/refs -- intentional stable-subscription pattern
  ref.current = handler;

  useEffect(() => {
    if (!frameHandlers.has(type)) frameHandlers.set(type, new Set());
    const fn = (f: InboundFrame) => ref.current(f as Extract<InboundFrame, { type: T }>);
    frameHandlers.get(type)!.add(fn);
    if (!ws && !retryTimeout) connect();
    return () => {
      frameHandlers.get(type)?.delete(fn);
    };
  }, [type]);
}

export function startWs() {
  listenForFocus();
  if (!ws && !retryTimeout) connect();
}
