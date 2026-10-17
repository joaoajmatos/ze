import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AboutPanel, useAskOverlay } from "@/features/ask-bar";
import { sendTurn } from "@/features/turn-stream";
import { useThread, useThreadHistory } from "@/entities/conversation";
import { screenSnapshot } from "@/entities/screen-context";
import { useSession } from "@/entities/session";
import { useConnectionState } from "@/shared/api";
import { askPath, placeOf } from "@/shared/config";
import { useSendNotice } from "@/shared/lib";
import { Control, Module } from "@/shared/ui";
import { Canvas } from "./Canvas";
import { ConfirmationPlacement } from "./ConfirmationPlacement";
import { RetryControl } from "./RetryControl";

/**
 * The contextual overlay behind the Ask bar. It is an ordinary Ask thread: the thread selected in Ask, so the
 * exchange shows in Ask and in Sessions. It draws the same canvas, compact, from the same conversation store.
 */
function AskOverlayPanel() {
  const navigate = useNavigate();
  const close = useAskOverlay((s) => s.close);
  const outbox = useAskOverlay((s) => s.outbox);
  const threadId = useSession((s) => s.threadId);
  const newSession = useSession((s) => s.newSession);
  const connection = useConnectionState();
  const isConnected = connection === "online";
  const thread = useThread(threadId);
  const { loadHistory } = useThreadHistory(threadId);

  const ready = thread.historyLoaded;
  const phase = thread.turn.phase;
  const running = phase === "awaiting" || phase === "thinking" || phase === "speaking";

  useEffect(() => {
    if (isConnected) void loadHistory();
  }, [isConnected, loadHistory]);

  // Messages already in the thread when the overlay opened stay in Ask; the baseline resets on New chat
  // because the thread changes and this component keys on it.
  const [baseline, setBaseline] = useState<Set<string> | null>(null);
  if (ready && baseline === null) setBaseline(new Set(thread.messages.map((m) => m.id)));
  const hidden = useMemo(() => baseline ?? new Set(thread.messages.map((m) => m.id)), [baseline, thread.messages]);

  useEffect(() => {
    if (!outbox || !ready || !isConnected || running) return;
    // Read the store, not the closure: a StrictMode double run must not send the same item twice.
    const item = useAskOverlay.getState().outbox;
    if (!item || item.id !== outbox.id) return;
    if (sendTurn(threadId, item.text, { explicitContext: item.context, workspacePlaced: item.workspacePlaced })) {
      useAskOverlay.getState().ack(item.id);
    }
  }, [outbox, ready, isConnected, running, threadId]);

  // The Ask bar stays the input, so focus stays there while the overlay is open and returns there on close.
  const dismiss = useCallback(() => {
    close();
    document.querySelector<HTMLElement>("[data-ask-input]")?.focus();
  }, [close]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") dismiss();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [dismiss]);

  const pathname = useLocation().pathname;
  const pickSuggestion = useCallback(
    (text: string) => {
      if (!useAskOverlay.getState().submit(text, screenSnapshot(pathname))) {
        useSendNotice.getState().showNotice("Ze has not sent your last message yet. Wait for it, then send this one.");
      }
    },
    [pathname],
  );

  const waitingFor = !outbox ? null : !isConnected ? (connection === "displaced" ? "Open in another window" : "Offline") : running ? "Ze is answering" : !ready ? "Loading the conversation" : null;

  return (
    <div className="ask-overlay" role="dialog" aria-label="Ask">
      <Module
        label="Ask"
        tools={
          <Control aria-label="Close" onClick={dismiss}>
            ✕
          </Control>
        }
      >
        <div className="ask-overlay-actions">
          <Control onClick={() => newSession()}>New chat</Control>
          <Control
            onClick={() => {
              navigate(askPath(threadId));
              close();
            }}
          >
            Open in Ask
          </Control>
        </div>
        <AboutPanel inputSelector="[data-ask-input]" onPick={pickSuggestion} />
        <div className="ask-overlay-list">
          <Canvas threadId={threadId} compact hiddenMessageIds={hidden} />
        </div>
        {outbox && waitingFor && (
          <p className="ask-overlay-queued" role="status">
            <span className="lbl">Waiting to send · {waitingFor}</span>
            {outbox.text}
          </p>
        )}
        <ConfirmationPlacement threadId={threadId} />
        <RetryControl threadId={threadId} />
      </Module>
    </div>
  );
}

export function AskOverlay() {
  const { pathname } = useLocation();
  const open = useAskOverlay((s) => s.open);
  const close = useAskOverlay((s) => s.close);
  const threadId = useSession((s) => s.threadId);
  const onAsk = placeOf(pathname)?.id === "ask";

  // Ask owns input there, and the same thread shows in full.
  useEffect(() => {
    if (open && onAsk) close();
  }, [open, onAsk, close]);

  if (!open || onAsk) return null;
  return <AskOverlayPanel key={threadId} />;
}
