import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAskOverlay } from "@/features/ask-bar";
import { ConfirmationCard } from "@/features/respond-to-confirmation";
import { useSession } from "@/entities/session";
import { askPath, placeOf } from "@/shared/config";
import { Control, Module } from "@/shared/ui";
import { useChatWorkspace } from "../model/useChatWorkspace";
import { ChatMessageList } from "./ChatMessageList";

/**
 * The contextual overlay behind the Ask bar. It is an ordinary Ask thread: the thread selected in
 * Ask, so the exchange shows in Ask and in Sessions. Full assembly in the overlay is phase 187.
 */
function AskOverlayPanel() {
  const navigate = useNavigate();
  const close = useAskOverlay((s) => s.close);
  const outbox = useAskOverlay((s) => s.outbox);
  const threadId = useSession((s) => s.threadId);
  const newSession = useSession((s) => s.newSession);

  const chat = useChatWorkspace({ active: true, context: outbox?.context, threadId });
  const { historyLoaded, isConnected, isThinking, sendMessage, messages } = chat;

  const ready = historyLoaded;

  // Messages already in the thread when the overlay opened stay in Ask; the baseline resets on New chat
  // because the thread changes and this component keys on it.
  const [baseline, setBaseline] = useState<Set<string> | null>(null);
  if (ready && baseline === null) setBaseline(new Set(messages.map((m) => String(m.id))));
  const visible = useMemo(() => (baseline ? messages.filter((m) => !baseline.has(String(m.id))) : []), [messages, baseline]);

  useEffect(() => {
    if (!outbox || !ready || !isConnected || isThinking) return;
    // Read the store, not the closure: a StrictMode double run must not send the same item twice.
    const item = useAskOverlay.getState().outbox;
    if (!item || item.id !== outbox.id) return;
    if (sendMessage(item.text)) useAskOverlay.getState().ack(item.id);
  }, [outbox, ready, isConnected, isThinking, sendMessage]);

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

  const waitingFor = !outbox ? null : !isConnected ? "Offline" : isThinking ? "Ze is answering" : !ready ? "Loading the conversation" : null;

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
          <Control
            onClick={() => {
              newSession();
            }}
          >
            New chat
          </Control>
          <Control
            onClick={() => {
              navigate(askPath(threadId));
              close();
            }}
          >
            Open in Ask
          </Control>
        </div>
        <ChatMessageList
          messages={visible}
          showTyping={chat.showTyping}
          typingText={chat.typingText}
          streamingText={chat.streamingText}
          deliveryFailed={chat.deliveryFailed}
          onRetry={chat.retry}
          className="ask-overlay-list"
        />
        {outbox && waitingFor && (
          <p className="ask-overlay-queued" role="status">
            <span className="lbl">Waiting to send · {waitingFor}</span>
            {outbox.text}
          </p>
        )}
        {chat.pendingConfirms.map((pending) => (
          <ConfirmationCard
            key={pending.id}
            title={pending.title}
            items={pending.items}
            source={pending.source}
            actions={pending.actions}
            disabled={pending.submitted}
            onRespond={(value, edits) => chat.respondToConfirm(pending.id, value, edits)}
          />
        ))}
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
