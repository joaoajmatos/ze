import type { MessageSchema as Message } from "@myguyze/ze-client";
import { useEffect, useRef, type ReactNode } from "react";
import { useChatAbout } from "@/features/ask-bar";
import { useSession } from "@/entities/session";
import { ChatErrorBoundary } from "@/shared/ui";
import { MessageBubble } from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";

interface ChatMessageListProps {
  messages: Message[];
  showTyping: boolean;
  typingText?: string | null;
  streamingText?: string | null;
  className?: string;
  deliveryFailed?: boolean;
  onRetry?: () => void;
  renderActions?: (message: Message) => ReactNode;
}

export function ChatMessageList({
  messages,
  showTyping,
  typingText,
  streamingText,
  className,
  deliveryFailed = false,
  onRetry,
  renderActions,
}: ChatMessageListProps) {
  const chatAbout = useChatAbout();
  const bottomRef = useRef<HTMLDivElement>(null);
  const highlightMessageId = useSession((s) => s.highlightMessageId);
  const setHighlightMessage = useSession((s) => s.setHighlightMessage);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, showTyping, streamingText, deliveryFailed]);

  useEffect(() => {
    if (!highlightMessageId) return;
    document
      .getElementById(`message-${highlightMessageId}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightMessageId, messages]);

  const unavailable =
    Boolean(highlightMessageId) &&
    messages.length > 0 &&
    !messages.some((m) => m.id === highlightMessageId);

  const streamingMessage: Message | null = streamingText?.trim()
    ? {
        id: "__streaming__",
        role: "assistant",
        text: streamingText,
        components: [],
        read: true,
        created_at: new Date().toISOString(),
        thread_id: null,
      }
    : null;

  return (
    <div
      className={className ?? "min-h-0 flex-1 space-y-4 overflow-y-auto py-2"}
      onClick={() => {
        if (highlightMessageId) setHighlightMessage(null);
      }}
    >
      {highlightMessageId && unavailable && (
        <p className="text-center text-xs text-smoke">
          The originating message is no longer available in this conversation.
        </p>
      )}
      {messages.map((msg) => (
        <ChatErrorBoundary key={msg.id}>
          <div id={`message-${msg.id}`}>
            <MessageBubble
              message={msg}
              highlighted={msg.id === highlightMessageId}
              actions={renderActions?.(msg)}
              onChatAbout={chatAbout}
            />
          </div>
        </ChatErrorBoundary>
      ))}
      {streamingMessage && (
        <ChatErrorBoundary key="__streaming__">
          <MessageBubble message={streamingMessage} />
        </ChatErrorBoundary>
      )}
      {showTyping && !streamingText && <TypingIndicator text={typingText} />}
      {deliveryFailed && !showTyping && (
        <div
          role="alert"
          className="mx-auto flex w-fit items-center gap-3 rounded-pill border border-foreground/15 px-4 py-2 text-xs text-foreground"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-destructive flex-shrink-0" />
          <span>Something went wrong. Ze did not reply.</span>
          {onRetry && (
            <button type="button" onClick={onRetry} className="text-plum-voltage underline">
              Retry
            </button>
          )}
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
