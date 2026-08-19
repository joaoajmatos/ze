import { useEffect, useMemo, useState } from "react";
import { ChatMessageList, ChatInput, ConfirmBar } from "@/entities/message";
import type { ChatAttachment } from "@/entities/message";
import { placeWorkspaceFile, useWorkspaceModeMutation, useWorkspaceQuery } from "@/entities/workspace";
import { reconnect, send } from "@/shared/api";
import { useTopBarQuickActions } from "@/shared/lib";
import { useSendNotice } from "@/features/send-context-notice";
import { BackgroundBeamsCanvas } from "@/shared/effects/background-beams";
import { GlowingStars } from "@/shared/effects/glowing-stars";
import { WorkspaceModeSwitcher } from "@/widgets/workspace-management";
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
    pendingConfirm,
    sendMessage,
    respondToConfirm,
  } = useChatWorkspace();

  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [attaching, setAttaching] = useState(false);
  const [connTimedOut, setConnTimedOut] = useState(false);
  const workspaceStatus = useWorkspaceQuery(Boolean(pendingConfirm));
  const setWorkspaceMode = useWorkspaceModeMutation();
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
          <button
            onClick={() => send({ type: "command", name: "capabilities" })}
            className="px-4 py-2 rounded-pill border border-plum-voltage/50 text-plum-voltage text-xs hover:border-plum-voltage transition-colors"
          >
            What can you help me with?
          </button>
        </div>
      )}

      {!isEmpty && (
        <div className="relative z-10 flex-1 min-h-0 flex flex-col">
          <ChatMessageList
            messages={messages}
            showTyping={showTyping}
            typingText={typingText}
            streamingText={streamingText}
          />
        </div>
      )}

      {pendingConfirm && (
        <ConfirmBar
          prompt={pendingConfirm.prompt}
          actions={pendingConfirm.actions}
          onConfirm={respondToConfirm}
          editable={pendingConfirm.editable}
          proposed={pendingConfirm.proposed}
          modeSwitcher={
            workspaceStatus.data ? (
              <WorkspaceModeSwitcher
                compact
                mode={workspaceStatus.data.mode}
                disabled={setWorkspaceMode.isPending}
                onChange={(mode) => setWorkspaceMode.mutate(mode)}
              />
            ) : null
          }
        />
      )}

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
