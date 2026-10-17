import type { CardActionEvent } from "@myguyze/ze-ui/react";
import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useDecideHeldWriteMutation } from "@/entities/confirmation";
import { useLoopTransitionMutation } from "@/entities/loop";
import { useSession } from "@/entities/session";
import { send } from "@/shared/api";
import { useSendNotice } from "@/shared/lib";
import { claimHref } from "../lib/claimHref";

/** Resolves true when the call went through, false when it failed. */
async function accepted(call: Promise<unknown>): Promise<boolean> {
  try {
    await call;
    return true;
  } catch {
    return false;
  }
}

/** Runs a claim card's closed-set intent with the call the app already has for it. */
export function useCardActions(): (action: CardActionEvent) => Promise<boolean> {
  const navigate = useNavigate();
  const threadId = useSession((s) => s.threadId);
  const showNotice = useSendNotice((s) => s.showNotice);
  const loopTransition = useLoopTransitionMutation();
  const decideHeldWrite = useDecideHeldWriteMutation();

  return useCallback(
    async ({ intent, ref_id, subject }: CardActionEvent) => {
      switch (intent) {
        case "confirm_loop":
          return accepted(loopTransition.mutateAsync({ loopId: ref_id, kind: "confirm" }));
        case "drop_loop":
          return accepted(loopTransition.mutateAsync({ loopId: ref_id, kind: "drop" }));
        case "approve_held_write":
          return accepted(decideHeldWrite.mutateAsync({ requestId: ref_id, choice: "approve" }));
        case "deny_held_write":
          return accepted(decideHeldWrite.mutateAsync({ requestId: ref_id, choice: "deny" }));
        case "approve_gate":
          if (!send({ type: "action", payload: `goal:approve:${ref_id}`, thread_id: threadId })) {
            showNotice("Not connected. Retry when Ze reconnects.");
            return false;
          }
          return true;
        case "open": {
          const href = claimHref(subject, ref_id);
          if (href) navigate(href);
          return true;
        }
      }
      return false;
    },
    [decideHeldWrite, loopTransition, navigate, showNotice, threadId],
  );
}
