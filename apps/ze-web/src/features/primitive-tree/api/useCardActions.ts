import type { CardActionEvent } from "@myguyze/ze-ui/react";
import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useDecideHeldWriteMutation } from "@/entities/confirmation";
import { useSession } from "@/entities/session";
import { useLoopTransitionMutation } from "@/entities/loop";
import { send } from "@/shared/api";
import { useSendNotice } from "@/shared/lib";
import { claimHref } from "../lib/claimHref";

/** Runs a claim card's closed-set intent with the call the app already has for it. */
export function useCardActions(): (action: CardActionEvent) => void {
  const navigate = useNavigate();
  const threadId = useSession((s) => s.threadId);
  const showNotice = useSendNotice((s) => s.showNotice);
  const loopTransition = useLoopTransitionMutation();
  const decideHeldWrite = useDecideHeldWriteMutation();

  return useCallback(
    ({ intent, ref_id, subject }: CardActionEvent) => {
      switch (intent) {
        case "confirm_loop":
          loopTransition.mutate({ loopId: ref_id, kind: "confirm" });
          return;
        case "drop_loop":
          loopTransition.mutate({ loopId: ref_id, kind: "drop" });
          return;
        case "approve_held_write":
          decideHeldWrite.mutate({ requestId: ref_id, choice: "approve" });
          return;
        case "deny_held_write":
          decideHeldWrite.mutate({ requestId: ref_id, choice: "deny" });
          return;
        case "approve_gate":
          if (!send({ type: "action", payload: `goal:approve:${ref_id}`, thread_id: threadId })) {
            showNotice("Not connected. Retry when Ze reconnects.");
          }
          return;
        case "open": {
          const href = claimHref(subject, ref_id);
          if (href) navigate(href);
          return;
        }
      }
    },
    [decideHeldWrite, loopTransition, navigate, showNotice, threadId],
  );
}
