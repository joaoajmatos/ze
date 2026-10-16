import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ChatInput, type ChatAttachment } from "./ChatInput";
import { ChatMessageList } from "./ChatMessageList";
import { placeWorkspaceFile } from "@/entities/workspace";
import { reconnect } from "@/shared/api";
import { useTopBarQuickActions } from "@/shared/lib";
import { useSendNotice } from "@/shared/lib";
import { ConfirmationCard } from "@/features/respond-to-confirmation";
import { ReplyActions, RollbackNotice } from "@/features/reply-feedback";
import { RetryButton, useRetryReply } from "@/features/retry-reply";
import { useMessageFeedbackQuery } from "@/entities/message-feedback";
import { BackgroundBeamsCanvas } from "@/shared/effects/background-beams";
import { GlowingStars } from "@/shared/effects/glowing-stars";
import { useChatWorkspace } from "../model/useChatWorkspace";
import { ChatLayout } from "./ChatLayout";
import { ChatSidePanel } from "./ChatSidePanel";
import { ChatSidePanelQuickActions } from "./ChatSidePanelQuickActions";

type ConnectionState = "connecting" | "connected" | "disconnected";

export function ChatWorkspace() {
  const {
    threadId,
    messages,
    showTyping,
    typingText,
    streamingText,
    isThinking,
    isConnected,
    deliveryFailed,
    pendingConfirms,
    sendMessage,
    retry,
    removeMessage,
    respondToConfirm,
  } = useChatWorkspace();

  const [searchParams] = useSearchParams();
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [attaching, setAttaching] = useState(false);
  const [connTimedOut, setConnTimedOut] = useState(false);
  const connState: ConnectionState =
    isConnected ? "connected" : connTimedOut ? "disconnected" : "connecting";

  const quickActions = useMemo(() => <ChatSidePanelQuickActions />, []);
  useTopBarQuickActions(quickActions);

  const assistantMessageIds = useMemo(
    () =>
      messages
        .filter((m) => m.role === "assistant" && m.id && m.id !== "__streaming__")
        .map((m) => String(m.id)),
    [messages],
  );

  const { byId: feedbackById } = useMessageFeedbackQuery(assistantMessageIds);
  const latestAssistantId = assistantMessageIds.at(-1) ?? null;
  const { retry: retryReply, retrying } = useRetryReply({
    threadId,
    onSuperseded: (messageId) => removeMessage(messageId),
    onNotice: (text) => useSendNotice.getState().showNotice(text),
  });

  const renderActions = useCallback(
    (message: { id: string; role: string }) => {
      if (message.role !== "assistant" || message.id === "__streaming__") return null;
      const id = String(message.id);
      const feedback = feedbackById.get(id);
      return (
        <>
          <RollbackNotice
              rollback={feedback?.rollback}
              busy={feedback?.retry?.reason_code === "busy"}
            />
          <ReplyActions
            messageId={id}
            feedback={feedback}
            retry={
              <RetryButton
                eligibility={feedback?.retry}
                isLatest={id === latestAssistantId}
                connected={isConnected}
                busy={isThinking}
                retrying={retrying}
                onRetry={(plan) => retryReply(id, plan)}
              />
            }
          />
        </>
      );
    },
    [feedbackById, latestAssistantId, isConnected, isThinking, retrying, retryReply],
  );

  useEffect(() => {
    if (isConnected) return;
    const disconnectTimer = setTimeout(() => setConnTimedOut(true), 10_000);
    return () => clearTimeout(disconnectTimer);
  }, [isConnected]);

  function handleSend() {
    if (sendMessage(input, attachments.map((a) => ({ path: a.path, size: a.size })))) {
      setInput("");
      setAttachments([]);
    }
  }

  async function handlePickFile(file: File) {
    setAttaching(true);
    try {
      const placed = await placeWorkspaceFile(file);
      setAttachments((prev) => [
        ...prev,
        { path: placed.path, size: placed.size, name: file.name },
      ]);
    } catch {
      useSendNotice.getState().showNotice("Could not place the file in the workspace.");
    } finally {
      setAttaching(false);
    }
  }

  const isEmpty = messages.length === 0 && connState === "connected";

  return (
    <ChatLayout sidebar={<ChatSidePanel threadId={threadId} assistantMessageIds={assistantMessageIds} />}>
      <BackgroundBeamsCanvas className="opacity-40" />

      {connState === "connecting" && (
        <div className="relative z-10 mb-3 flex w-full items-center gap-2 rounded-pill border border-amber-spark/40 px-4 py-2 text-xs text-amber-spark">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-spark animate-pulse" />
          Connecting to Ze…
        </div>
      )}
      {connState === "disconnected" && (
        <div className="relative z-10 mb-3 flex w-full items-center justify-between rounded-pill border border-foreground/15 px-4 py-2 text-xs text-foreground">
          <span className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-destructive" />
            Could not connect.
          </span>
          <button
            onClick={() => {
              setConnTimedOut(false);
              reconnect();
            }}
            className="text-plum-voltage underline"
          >
            Retry
          </button>
        </div>
      )}

      {isEmpty && (
        <div className="relative z-10 flex-1 flex flex-col items-center justify-center gap-6 motion-safe:[animation:sky-settle_600ms_ease-out]">
          <GlowingStars className="rounded-pill" count={80} />
          <p className="font-display text-[48px] font-medium tracking-tight text-foreground leading-none select-none">
            Ze
          </p>
          <p className="text-sm text-smoke">Your personal AI assistant</p>
        </div>
      )}

      {!isEmpty && (
        <div className="relative z-10 flex-1 min-h-0 flex flex-col">
          <ChatMessageList
            messages={messages}
            showTyping={showTyping}
            typingText={typingText}
            streamingText={streamingText}
            deliveryFailed={deliveryFailed}
            onRetry={retry}
            renderActions={renderActions}
          />
        </div>
      )}

      {pendingConfirms.map((pendingConfirm) => (
        <ConfirmationCard
          key={pendingConfirm.id}
          title={pendingConfirm.title}
          items={pendingConfirm.items}
          source={pendingConfirm.source}
          actions={pendingConfirm.actions}
          disabled={pendingConfirm.submitted}
          highlighted={searchParams.get("confirm") === pendingConfirm.id}
          onRespond={(value, edits) => respondToConfirm(pendingConfirm.id, value, edits)}
        />
      ))}

      <div className="relative z-10 flex-shrink-0">
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          disabled={isThinking}
          attachments={attachments}
          onPickFile={handlePickFile}
          onRemoveAttachment={(path) =>
            setAttachments((prev) => prev.filter((a) => a.path !== path))
          }
          attaching={attaching}
        />
      </div>
    </ChatLayout>
  );
}
