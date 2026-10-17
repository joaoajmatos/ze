import type { WsScreenContext } from "@myguyze/ze-client";
import { useEffect, useRef, type ReactNode } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { AnswerGateFrameHandler } from "@/features/answer-gate";
import { AskBar, useAskOverlay, useAskShortcut } from "@/features/ask-bar";
import { RefreshHandler } from "@/features/invalidate-on-ws-refresh";
import { ConfirmationFrameHandler } from "@/features/respond-to-confirmation";
import { TraceFrameHandler } from "@/features/trace-state";
import { sendTurn, TurnFrameHandler } from "@/features/turn-stream";
import { usePresence } from "@/entities/presence";
import { screenSnapshot } from "@/entities/screen-context";
import { useSession } from "@/entities/session";
import { useConnectionState, useFrame } from "@/shared/api";
import { placeOf } from "@/shared/config";
import { BreadcrumbProvider, PageHeaderProvider, TopBarActionsProvider, useNarrow, useRailSlot } from "@/shared/lib";
import { useTopBarActions } from "@/shared/lib/top-bar-actions";
import { NoticeBanner, Presence, type PresenceHandle } from "@/shared/ui";
import { BottomBar } from "./BottomBar";
import { DISPLACED_LINE, DisplacedNotice } from "./DisplacedNotice";
import { Strip } from "./Strip";
import { TopBar } from "./TopBar";

/** Interim pages still register quick actions; show them above their content until their place replaces them. */
function InterimActions() {
  const { quickActions } = useTopBarActions();
  if (!quickActions) return null;
  return <div className="interim-actions">{quickActions}</div>;
}

function Shell({ overlay }: { overlay?: ReactNode }) {
  const narrow = useNarrow();
  const { pathname } = useLocation();
  const onAsk = placeOf(pathname)?.id === "ask";
  const threadId = useSession((s) => s.threadId);
  const { orb, phrase } = usePresence(threadId);
  const overlayOpen = useAskOverlay((s) => s.open);
  const setRailSlot = useRailSlot((s) => s.setElement);

  // On Ask the message goes straight to the selected thread; on every other place it queues in the overlay.
  const askSubmit = (text: string, explicit: WsScreenContext | null, placed?: { path: string; size: number }[]) =>
    onAsk
      ? sendTurn(threadId, text, { explicitContext: explicit, workspacePlaced: placed })
      : useAskOverlay.getState().submit(text, screenSnapshot(pathname), placed);

  const connection = useConnectionState();
  const presenceRef = useRef<PresenceHandle>(null);
  const bellRef = useRef<HTMLDivElement>(null);
  useAskShortcut();

  useFrame("notification", () => {
    if (bellRef.current) presenceRef.current?.glance(bellRef.current);
  });

  // "Chat about this" asks the orb to look at the component the person chose. It wins over the
  // overlay's own glance at its panel, which would otherwise pull the eye away a frame later.
  const glanceTick = useAskOverlay((s) => s.glanceTick);
  const lastGlanceTick = useRef(0);
  useEffect(() => {
    if (glanceTick === lastGlanceTick.current) return;
    lastGlanceTick.current = glanceTick;
    const target = useAskOverlay.getState().glanceTarget;
    if (target) presenceRef.current?.glance(target);
  }, [glanceTick]);

  const overlayGlanceSkipped = useRef(0);
  useEffect(() => {
    if (!overlayOpen) return;
    if (useAskOverlay.getState().glanceTick !== overlayGlanceSkipped.current && useAskOverlay.getState().glanceTarget) {
      overlayGlanceSkipped.current = useAskOverlay.getState().glanceTick;
      return;
    }
    // The panel mounts on the next commit; look at it once it is there.
    const id = requestAnimationFrame(() => {
      const panel = document.querySelector(".ask-overlay");
      if (panel) presenceRef.current?.glance(panel);
    });
    return () => cancelAnimationFrame(id);
  }, [overlayOpen]);

  return (
    <div className={`shell ${onAsk ? "on-ask" : ""}`}>
      <TopBar ref={bellRef} showTabs={!narrow} />
      <Strip />
      <DisplacedNotice />
      <NoticeBanner />
      <main className="main main-places">
        <aside className="rail" aria-label="Ze status">
          <Presence ref={presenceRef} state={orb} phrase={phrase} compact={narrow} />
          <div className="rail-slot" ref={setRailSlot} />
        </aside>
        <div className="place">
          <InterimActions />
          <Outlet />
        </div>
      </main>
      <AskBar onSubmit={askSubmit} disabledReason={connection === "displaced" ? DISPLACED_LINE : null} />
      {narrow && <BottomBar />}
      <RefreshHandler />
      <ConfirmationFrameHandler />
      <TurnFrameHandler />
      <TraceFrameHandler />
      <AnswerGateFrameHandler />
      {overlay}
    </div>
  );
}

export function AppShell({ overlay }: { overlay?: ReactNode }) {
  return (
    <BreadcrumbProvider>
      <PageHeaderProvider>
        <TopBarActionsProvider>
          <Shell overlay={overlay} />
        </TopBarActionsProvider>
      </PageHeaderProvider>
    </BreadcrumbProvider>
  );
}
