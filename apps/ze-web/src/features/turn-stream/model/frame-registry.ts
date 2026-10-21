import type { WsInboundFrame } from "@myguyze/ze-client";

export type FrameType = WsInboundFrame["type"];

export interface FrameEntry {
  frame: FrameType;
  /** The file holding the `useFrame` call. `null` for a frame the client keeps no state for. */
  file: string | null;
  slice: string;
  role: "state-owner" | "listener" | "none";
  reason: string;
}

/**
 * Every `useFrame` call site, with why it exists. A frame has exactly one state owner; a listener
 * reacts for its own reason and never writes the conversation store. `frame-coverage.test.ts`
 * fails when a call site is missing here.
 */
export const FRAME_REGISTRY: FrameEntry[] = [
  ...(["typing", "token", "message", "edit", "error", "message_superseded", "message_rollback"] as const).map(
    (frame): FrameEntry => ({
      frame,
      file: "features/turn-stream/ui/TurnFrameHandler.tsx",
      slice: "entities/conversation",
      role: "state-owner",
      reason: "the reducer owns the thread's turn and messages",
    }),
  ),
  ...(["confirm_request", "confirm_cancel"] as const).map(
    (frame): FrameEntry => ({
      frame,
      file: "features/respond-to-confirmation/ui/ConfirmationFrameHandler.tsx",
      slice: "features/respond-to-confirmation",
      role: "state-owner",
      reason: "the pending-confirmation store keeps every thread's open card",
    }),
  ),
  {
    frame: "trace_update",
    file: "features/trace-state/model/useTraceSocket.ts",
    slice: "features/trace-state",
    role: "state-owner",
    reason: "the trace store merges partial and final traces",
  },
  {
    frame: "refresh",
    file: "features/invalidate-on-ws-refresh/ui/RefreshHandler.tsx",
    slice: "features/invalidate-on-ws-refresh",
    role: "state-owner",
    reason: "refresh invalidates the screen's queries",
  },
  {
    frame: "notification",
    file: "features/invalidate-on-ws-refresh/ui/RefreshHandler.tsx",
    slice: "features/invalidate-on-ws-refresh",
    role: "state-owner",
    reason: "a notification invalidates the notification cache",
  },
  {
    frame: "ui_action_result",
    file: "features/primitive-tree/api/usePrimitiveActions.ts",
    slice: "features/primitive-tree",
    role: "state-owner",
    reason: "the pending button action resolves on its result and shows the line",
  },
  { frame: "pong", file: null, slice: "shared/api", role: "none", reason: "answers a ping; the client keeps no state for it" },
  ...([
    ["typing", "features/respond-to-confirmation/ui/ConfirmationFrameHandler.tsx", "the server resuming the thread acknowledges a confirmation"],
    ["token", "features/respond-to-confirmation/ui/ConfirmationFrameHandler.tsx", "the server resuming the thread acknowledges a confirmation"],
    ["message", "features/respond-to-confirmation/ui/ConfirmationFrameHandler.tsx", "the server resuming the thread acknowledges a confirmation"],
    ["message", "features/invalidate-on-ws-refresh/ui/RefreshHandler.tsx", "World reloads when a reply may have changed what it shows"],
    ["notification", "widgets/app-shell/ui/AppShell.tsx", "the orb glances at the bell"],
    ["confirm_request", "features/turn-stream/ui/TurnFrameHandler.tsx", "a waiting confirmation pauses the delivery watchdog"],
    ["confirm_cancel", "features/primitive-tree/api/usePrimitiveActions.ts", "a cancelled gate settles the pending button press"],
  ] as const).map(
    ([frame, file, reason]): FrameEntry => ({ frame, file, slice: file.split("/").slice(0, 2).join("/"), role: "listener", reason }),
  ),
];
