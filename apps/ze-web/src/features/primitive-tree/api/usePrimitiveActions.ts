import type { WsScreenContext } from "@myguyze/ze-client";
import type { PrimitiveAction } from "@myguyze/ze-ui";
import type { PrimitiveRendererActions } from "@myguyze/ze-ui/react";
import { useEffect, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useOnboardingSession } from "@/entities/onboarding-session";
import { useSession } from "@/entities/session";
import { send, useFrame, useWsStore } from "@/shared/api";
import { placeOf } from "@/shared/config";
import { useSendNotice } from "@/shared/lib";
import { useTurnSender } from "../model/turn-sender";

const NOT_CONNECTED_NOTICE = "Not connected. Retry when Ze reconnects.";
// The server holds an irreversible write's confirmation for 15 minutes; wait a little longer than that.
const RESULT_TIMEOUT_MS = 16 * 60_000;

const COMPOSE_TEXT = {
  slipping: "What's slipping?",
  decisions: "What should I decide today?",
} as const;

type ComposeAction = Extract<PrimitiveAction, { kind: "compose" }>;

function composeText({ compose, topic }: ComposeAction): string {
  return compose === "topic" ? `How is ${topic ?? "that"} going?` : COMPOSE_TEXT[compose];
}

function isPlaceRoute(route: string): boolean {
  if (!route.startsWith("/") || route.startsWith("//")) return false;
  const pathname = route.split(/[?#]/)[0];
  return pathname === "/" || placeOf(pathname) !== null;
}

interface Pending {
  id: string;
  settle: (ok: boolean) => void;
}

/** Runs a button's typed action: `ask`, `compose` and `navigate` stay in the client, `tool` goes to the server's gates. */
export function usePrimitiveActions(): PrimitiveRendererActions {
  const sessionId = useOnboardingSession((s) => s.sessionId);
  const completed = useOnboardingSession((s) => s.completed);
  const threadId = useSession((s) => s.threadId);
  const showNotice = useSendNotice((s) => s.showNotice);
  const navigate = useNavigate();
  const sendTurn = useTurnSender();
  const pending = useRef<Pending | null>(null);

  useFrame("ui_action_result", (frame) => {
    const current = pending.current;
    if (!current || current.id !== frame.id) return;
    showNotice(frame.line);
    current.settle(frame.ok);
  });

  // A result sent just before the socket dropped is never replayed, so a dropped socket settles the press.
  const isConnected = useWsStore((s) => s.isConnected);
  useEffect(() => {
    if (!isConnected) pending.current?.settle(false);
  }, [isConnected]);

  // The server cancelled the gate (timeout or a newer turn) without a result for this press.
  useFrame("confirm_cancel", (frame) => {
    if (frame.reason !== "answered" && pending.current?.id === frame.id) pending.current.settle(false);
  });

  return useMemo(() => {
    function runTool(action: Extract<PrimitiveAction, { kind: "tool" }>): Promise<boolean> {
      if (pending.current) return Promise.resolve(false);
      const id = crypto.randomUUID();
      if (!send({ type: "ui_action", id, thread_id: threadId, action })) {
        showNotice(NOT_CONNECTED_NOTICE);
        return Promise.resolve(false);
      }
      return new Promise<boolean>((resolve) => {
        const timer = setTimeout(() => current.settle(false), RESULT_TIMEOUT_MS);
        const current: Pending = {
          id,
          settle: (ok) => {
            clearTimeout(timer);
            pending.current = null;
            resolve(ok);
          },
        };
        pending.current = current;
      });
    }

    return {
      onAction: (action: PrimitiveAction): boolean | Promise<boolean> => {
        switch (action.kind) {
          case "ask":
            return sendTurn ? sendTurn(threadId, action.text) : false;
          case "compose": {
            const context = { origin: "preset", compose: action.compose, topic: action.topic } as WsScreenContext;
            return sendTurn ? sendTurn(threadId, composeText(action), { explicitContext: context }) : false;
          }
          case "navigate":
            if (!isPlaceRoute(action.route)) {
              showNotice("That link can't be opened.");
              return false;
            }
            navigate(action.route);
            return true;
          case "tool":
            return runTool(action);
        }
      },
      onFormSubmit: (formId: string, values: Record<string, string>) => {
        if (sessionId && !completed && formId) {
          return send({ type: "component_submit", session_id: sessionId, step_id: formId, values });
        }
        if (formId) {
          return send({ type: "component_submit", step_id: formId, values, thread_id: threadId });
        }
        return send({ type: "message", text: `[form] ${JSON.stringify(values)}`, thread_id: threadId });
      },
      onDisconnected: () => {
        showNotice(NOT_CONNECTED_NOTICE);
      },
    };
  }, [completed, navigate, sendTurn, sessionId, showNotice, threadId]);
}
