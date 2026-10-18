import { useConversation, type ThreadState } from "@/entities/conversation";
import { useSession } from "@/entities/session";
import { useWsStore } from "@/shared/api";

/** Longest silence (no reply, typing or token) tolerated before the client checks stored history instead. */
export const DELIVERY_WATCHDOG_MS = 120_000;

const isRunning = (t: ThreadState | undefined) =>
  t !== undefined && (t.turn.phase === "awaiting" || t.turn.phase === "thinking" || t.turn.phase === "speaking");

const apply = (event: Parameters<ReturnType<typeof useConversation.getState>["apply"]>[0]) =>
  useConversation.getState().apply(event, { activeThreadId: useSession.getState().threadId });

/**
 * Bounded wait: a turn ends in a visible reply or a visible failure, never an indefinite spinner.
 * One timer per running thread. A thread paused on a confirmation has none, so a card open for
 * fifteen minutes never reads as an undelivered reply.
 */
export function startDeliveryWatchdog({ reload }: { reload: (threadId: string) => Promise<unknown> }): () => void {
  const timers = new Map<string, ReturnType<typeof setTimeout>>();

  const disarm = (id: string) => {
    const t = timers.get(id);
    if (t) clearTimeout(t);
    timers.delete(id);
  };
  const arm = (id: string, ms: number) => {
    disarm(id);
    timers.set(id, setTimeout(() => void onDeadline(id), ms));
  };
  const failIfStillWaiting = (id: string) => {
    if (isRunning(useConversation.getState().byThread[id])) apply({ type: "delivery_failed", threadId: id });
  };
  const onDeadline = async (id: string) => {
    timers.delete(id);
    const thread = useConversation.getState().byThread[id];
    if (!isRunning(thread)) return;
    const idle = Date.now() - thread!.turn.activityAt;
    if (idle < DELIVERY_WATCHDOG_MS) {
      arm(id, DELIVERY_WATCHDOG_MS - idle);
      return;
    }
    await reload(id);
    failIfStillWaiting(id);
  };

  const sync = (next: Record<string, ThreadState>, prev: Record<string, ThreadState>) => {
    for (const [id, t] of Object.entries(next)) {
      const before = prev[id];
      if (!isRunning(t)) {
        disarm(id);
      } else if (!isRunning(before) || before!.turn.activityAt !== t.turn.activityAt) {
        arm(id, DELIVERY_WATCHDOG_MS);
      }
    }
  };
  const unsubscribeThreads = useConversation.subscribe((s, p) => sync(s.byThread, p.byThread));

  // The socket dropped mid-turn. Once reconnected, the stored reply either is in history or the turn is lost.
  const unsubscribeWs = useWsStore.subscribe((s) => {
    if (!s.isConnected) return;
    for (const id of Object.keys(s.interruptedThreads)) {
      s.clearThreadInterrupted(id);
      void reload(id).then(() => failIfStillWaiting(id));
    }
  });

  return () => {
    unsubscribeThreads();
    unsubscribeWs();
    for (const id of [...timers.keys()]) disarm(id);
  };
}
