import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useParams } from "react-router-dom";
import { Canvas, ConfirmationPlacement, RetryControl, TraceModule, TraceSheet, type WhyTarget } from "@/widgets/assemble";
import { SessionsRail } from "@/widgets/sessions-rail";
import { TryChips } from "@/widgets/try-chips";
import { useAskOverlay, useChatAbout } from "@/features/ask-bar";
import { sendTurn, type SendTurnOptions } from "@/features/turn-stream";
import { useThread, useThreadHistory } from "@/entities/conversation";
import { useOnboardingSession } from "@/entities/onboarding-session";
import { useSession } from "@/entities/session";
import { useConnectionState } from "@/shared/api";
import { useNarrow, useRailSlot } from "@/shared/lib";
import { Control } from "@/shared/ui";

const ONBOARDING_KEY = "ze_onboarding_opened";

function rememberedSession(): string | null {
  try {
    return localStorage.getItem(ONBOARDING_KEY);
  } catch {
    return null;
  }
}
function remember(sessionId: string) {
  try {
    localStorage.setItem(ONBOARDING_KEY, sessionId);
  } catch {
    // The page still works; a reload may select the onboarding thread once more.
  }
}

/** Ask: the rail (try, sessions), the canvas for the selected thread, and the trace of the selected reply. */
export function AskPage() {
  const threadId = useSession((s) => s.threadId);
  // Per-thread view state (selected reply, open "Why?") resets by remounting on a thread change.
  return <AskThread key={threadId} threadId={threadId} />;
}

function AskThread({ threadId }: { threadId: string }) {
  const { threadId: urlThread } = useParams<{ threadId: string }>();
  const selectSession = useSession((s) => s.selectSession);
  const thread = useThread(threadId);
  const { loadHistory } = useThreadHistory(threadId);
  const connection = useConnectionState();
  const narrow = useNarrow();
  const railSlot = useRailSlot((s) => s.element);
  const chatAbout = useChatAbout();
  const draft = useAskOverlay((s) => s.draft);
  const onboardingId = useOnboardingSession((s) => s.sessionId);
  const onboardingDone = useOnboardingSession((s) => s.completed);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [why, setWhy] = useState<{ messageId: string; target: WhyTarget } | null>(null);
  const [sheet, setSheet] = useState(false);

  useEffect(() => {
    if (urlThread && useSession.getState().threadId !== urlThread) selectSession(urlThread);
  }, [urlThread, selectSession]);

  useEffect(() => {
    if (connection === "online") void loadHistory();
  }, [connection, loadHistory]);

  const running = ["awaiting", "thinking", "speaking"].includes(thread.turn.phase);
  const onboardingThread = onboardingId && !onboardingDone ? `onboarding:${onboardingId}` : null;

  // The server re-sends the onboarding view on every connect until it completes, so open it once per session id.
  useEffect(() => {
    if (!onboardingId || onboardingDone || !onboardingThread) return;
    // Only from an empty thread: never move someone out of a conversation they are in.
    if (urlThread || draft.trim() || running || !thread.historyLoaded || thread.messages.length > 0 || rememberedSession() === onboardingId) return;
    remember(onboardingId);
    selectSession(onboardingThread);
  }, [onboardingId, onboardingDone, onboardingThread, urlThread, draft, running, thread.historyLoaded, thread.messages.length, selectSession]);

  const send = useCallback((text: string, context: SendTurnOptions["explicitContext"]) => sendTurn(threadId, text, { explicitContext: context }), [threadId]);

  const openWhy = (messageId: string, target: WhyTarget) => {
    setSelectedId(messageId);
    setWhy({ messageId, target });
    if (narrow) setSheet(true);
  };
  const empty = thread.messages.length === 0 && thread.historyLoaded;

  const rail = (
    <div className="ask-rail" role="region" aria-label="Ask">
      <TryChips onSend={(text, context) => send(text, context)} disabled={connection !== "online" || running} />
      {onboardingThread && threadId !== onboardingThread && (
        <button type="button" className="ctl-text ask-continue" onClick={() => selectSession(onboardingThread)}>
          <span className="lbl on">Continue getting to know you</span>
        </button>
      )}
      <SessionsRail />
    </div>
  );

  return (
    <div className="ask-page">
      {railSlot ? createPortal(rail, railSlot) : rail}
      <section className="ask-main" aria-label="Conversation">
        {empty && <p className="muted">Ask Ze anything below. Its answer comes back as modules you can pin, dismiss or ask about.</p>}
        <Canvas
          threadId={threadId}
          compact={narrow}
          selectedMessageId={selectedId}
          onSelect={setSelectedId}
          onChatAbout={chatAbout}
          onWhy={openWhy}
        />
        <ConfirmationPlacement threadId={threadId} />
        <RetryControl threadId={threadId} />
        {narrow && (
          <Control onClick={() => setSheet(true)} aria-label="Open the trace of the selected reply">
            Trace
          </Control>
        )}
      </section>
      {!narrow && (
        <aside className="ask-trace" aria-label="Trace">
          <TraceModule threadId={threadId} messageId={selectedId} openSection={why?.messageId === selectedId ? why?.target.section : null} highlight={why?.target.highlight ?? []} />
        </aside>
      )}
      {narrow && sheet && <TraceSheet threadId={threadId} messageId={selectedId} target={why?.target ?? null} onClose={() => setSheet(false)} />}
    </div>
  );
}
