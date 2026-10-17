import type {
  MessageSchema as Message,
  UndoPlanEntryResponse,
  WsInboundFrame,
  WsScreenContext,
} from "@myguyze/ze-client";

export type TurnPhase = "idle" | "awaiting" | "thinking" | "speaking" | "paused" | "failed";

export interface SentTurn {
  text: string;
  context: WsScreenContext;
  workspacePlaced?: { path: string; size: number }[];
  /** Client time of the first send; the Signal path's zero. A resend keeps it. */
  at: number;
}

export type TurnOutcome =
  | { kind: "busy"; detail: string }
  | { kind: "error"; detail: string }
  | { kind: "retry_failed"; detail: string }
  | { kind: "retry_partial"; detail: string; plan?: UndoPlanEntryResponse[] }
  | { kind: "rolled_back_retry_failed"; detail: string };

export interface ThreadState {
  messages: Message[];
  historyLoaded: boolean;
  turn: {
    phase: TurnPhase;
    typingText: string | null;
    streamingText: string;
    activityAt: number;
    lastSent: SentTurn | null;
  };
  lastOutcome: TurnOutcome | null;
  lastMessageAt: number | null;
  lastError: { detail: string; code: string | null; at: number } | null;
  attention: boolean;
}

export interface ConversationState {
  byThread: Record<string, ThreadState>;
}

type Frame<K extends WsInboundFrame["type"]> = Extract<WsInboundFrame, { type: K }>;

export type ConversationEvent =
  | Frame<"typing">
  | Frame<"token">
  | Frame<"message">
  | Frame<"edit">
  | Frame<"error">
  | Frame<"message_superseded">
  | Frame<"message_rollback">
  | {
      type: "sent";
      threadId: string;
      text: string;
      context: WsScreenContext;
      workspacePlaced?: { path: string; size: number }[];
      resend?: boolean;
    }
  | { type: "retry_sent"; threadId: string; messageId: string }
  | { type: "history_loaded"; threadId: string; messages: Message[] }
  | { type: "delivery_failed"; threadId: string }
  | { type: "paused"; threadId: string }
  | { type: "resumed"; threadId: string }
  | { type: "opened"; threadId: string }
  | { type: "reset"; threadId: string };

export interface ReduceContext {
  activeThreadId: string | null;
}

export const LOCAL_ID_PREFIX = "local-";

export function emptyThread(): ThreadState {
  return {
    messages: [],
    historyLoaded: false,
    turn: { phase: "idle", typingText: null, streamingText: "", activityAt: 0, lastSent: null },
    lastOutcome: null,
    lastMessageAt: null,
    lastError: null,
    attention: false,
  };
}

const RUNNING: TurnPhase[] = ["awaiting", "thinking", "speaking"];
const isRunning = (t: ThreadState) => RUNNING.includes(t.turn.phase);

const byCreated = (a: Message, b: Message) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime();

function upsert(messages: Message[], m: Message): Message[] {
  const i = messages.findIndex((x) => x.id === m.id);
  if (i >= 0) {
    const next = [...messages];
    next[i] = m;
    return next;
  }
  return [...messages, m].sort(byCreated);
}

function endTurn(t: ThreadState, phase: TurnPhase = "idle"): ThreadState {
  return { ...t, turn: { ...t.turn, phase, typingText: null, streamingText: "" } };
}

/** Threads a frame without a `thread_id` can belong to: only the ones with a turn in flight. */
function targets(state: ConversationState, threadId: string | null | undefined): string[] {
  if (threadId) return [threadId];
  return Object.entries(state.byThread)
    .filter(([, t]) => isRunning(t))
    .map(([id]) => id);
}

function patch(state: ConversationState, id: string, fn: (t: ThreadState) => ThreadState): ConversationState {
  const cur = state.byThread[id] ?? emptyThread();
  return { byThread: { ...state.byThread, [id]: fn(cur) } };
}

export function reduce(state: ConversationState, event: ConversationEvent, now: number, ctx: ReduceContext): ConversationState {
  switch (event.type) {
    case "typing":
      return targets(state, event.thread_id).reduce(
        (s, id) =>
          patch(s, id, (t) =>
            t.turn.phase === "speaking" || t.turn.phase === "paused"
              ? { ...t, turn: { ...t.turn, typingText: event.text ?? null, activityAt: now } }
              : { ...t, turn: { ...t.turn, phase: "thinking", typingText: event.text ?? null, activityAt: now } },
          ),
        state,
      );
    case "token":
      return targets(state, event.thread_id).reduce(
        (s, id) =>
          patch(s, id, (t) => ({
            ...t,
            turn: { ...t.turn, phase: "speaking", streamingText: t.turn.streamingText + event.text, activityAt: now },
          })),
        state,
      );
    case "message": {
      const m = event.message;
      if (!m.thread_id) return state;
      return patch(state, m.thread_id, (t) => {
        const next: ThreadState = { ...t, messages: upsert(t.messages, m), lastMessageAt: now };
        if (m.role !== "assistant") return next;
        const settled = endTurn(next);
        return { ...settled, attention: m.thread_id === ctx.activeThreadId ? false : true };
      });
    }
    case "edit": {
      const targetsIds = event.thread_id ? [event.thread_id] : Object.keys(state.byThread);
      return targetsIds.reduce(
        (s, id) =>
          patch(s, id, (t) => ({
            ...t,
            messages: t.messages.map((m) =>
              m.id === event.id
                ? {
                    ...m,
                    ...(event.text != null && { text: event.text }),
                    ...(event.components != null && { components: event.components }),
                  }
                : m,
            ),
          })),
        state,
      );
    }
    case "error": {
      const ids = targets(state, event.thread_id);
      return ids.reduce((s, id) => {
        const detail = event.detail;
        return patch(s, id, (t) => {
          const withError: ThreadState = {
            ...t,
            lastError: { detail, code: event.code ?? null, at: now },
          };
          switch (event.code) {
            case "busy":
              return { ...withError, lastOutcome: { kind: "busy", detail } };
            case "retry_unavailable":
              return { ...endTurn(withError), lastOutcome: { kind: "error", detail: event.reason_text ?? "Ze cannot retry this reply." } };
            case "retry_partial":
              return {
                ...endTurn(withError),
                lastOutcome: { kind: "retry_partial", detail: detail || "Ze could not undo everything, so the original reply stays.", plan: event.plan ?? undefined },
              };
            case "retry_failed":
              return {
                ...endTurn(withError),
                lastOutcome: event.rolled_back
                  ? { kind: "rolled_back_retry_failed", detail: detail || "Ze undid the earlier actions but could not write a new reply." }
                  : { kind: "retry_failed", detail: "Retry failed. The original reply is unchanged." },
              };
            default:
              return endTurn(withError, isRunning(t) ? "failed" : "idle");
          }
        });
      }, state);
    }
    case "message_superseded": {
      const id = event.thread_id;
      const ids = id ? [id] : Object.keys(state.byThread);
      return ids.reduce(
        (s, tid) =>
          patch(s, tid, (t) => ({
            ...endTurn(t),
            messages: t.messages.map((m) => (m.id === event.message_id ? { ...m, replaced_by: event.replaced_by } : m)),
          })),
        state,
      );
    }
    case "message_rollback": {
      const ids = event.thread_id ? [event.thread_id] : Object.keys(state.byThread);
      return ids.reduce(
        (s, tid) =>
          patch(s, tid, (t) => {
            const marked = {
              ...t,
              messages: t.messages.map((m) => (m.id === event.message_id ? { ...m, rollback: event.rollback } : m)),
            };
            // A denied or expired paused retry ends here with no error frame.
            return event.rollback.state === "rolled_back_retry_failed" && isRunning(t) ? endTurn(marked) : marked;
          }),
        state,
      );
    }
    case "sent":
      return patch(state, event.threadId, (t) => {
        const last = [...t.messages].reverse().find((m) => m.role === "user");
        const keep = event.resend && last?.text === event.text;
        const messages = keep
          ? t.messages
          : upsert(t.messages, {
              id: `${LOCAL_ID_PREFIX}${now}-${t.messages.length}`,
              role: "user",
              text: event.text,
              components: [],
              read: true,
              created_at: new Date(now).toISOString(),
              thread_id: event.threadId,
            });
        const at = event.resend && t.turn.lastSent ? t.turn.lastSent.at : now;
        return {
          ...t,
          messages,
          lastOutcome: null,
          turn: {
            phase: "awaiting",
            typingText: null,
            streamingText: "",
            activityAt: now,
            lastSent: { text: event.text, context: event.context, workspacePlaced: event.workspacePlaced, at },
          },
        };
      });
    case "retry_sent":
      return patch(state, event.threadId, (t) => ({
        ...t,
        lastOutcome: null,
        turn: { ...t.turn, phase: "awaiting", typingText: null, streamingText: "", activityAt: now },
      }));
    case "history_loaded":
      return patch(state, event.threadId, (t) => {
        const userTexts = new Set(event.messages.filter((m) => m.role === "user").map((m) => m.text));
        const byId = new Map<string, Message>();
        for (const m of t.messages) {
          if (m.id.startsWith(LOCAL_ID_PREFIX) && userTexts.has(m.text)) continue;
          byId.set(m.id, m);
        }
        const known = new Set(t.messages.map((m) => m.id));
        for (const m of event.messages) byId.set(m.id, m);
        const merged = { ...t, historyLoaded: true, messages: [...byId.values()].sort(byCreated) };
        // A reload during a wait that finds a reply we never saw ends the wait.
        const arrived = event.messages.some((m) => m.role === "assistant" && !known.has(m.id));
        return arrived && isRunning(t) ? endTurn(merged) : merged;
      });
    case "delivery_failed":
      return patch(state, event.threadId, (t) => endTurn(t, "failed"));
    case "paused":
      return patch(state, event.threadId, (t) =>
        isRunning(t) ? { ...t, turn: { ...t.turn, phase: "paused" } } : t,
      );
    case "resumed":
      // Also from idle or failed: a confirmation replayed after a reload resumes a turn this client never saw start.
      return patch(state, event.threadId, (t) =>
        isRunning(t) ? t : { ...t, turn: { ...t.turn, phase: "awaiting", activityAt: now } },
      );
    case "opened":
      return patch(state, event.threadId, (t) => ({ ...t, attention: false }));
    case "reset":
      return { byThread: { ...state.byThread, [event.threadId]: emptyThread() } };
  }
}
