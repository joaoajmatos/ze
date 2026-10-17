import { RollbackNotice } from "@/features/reply-feedback";
import { RetryButton, useRetryReply } from "@/features/retry-reply";
import { useSession } from "@/entities/session";
import { send, useWsStore } from "@/shared/api";
import { useSendNotice } from "@/shared/lib";
import { Control } from "@/shared/ui";
import { useAssemble } from "../model/useAssemble";

/** Retry on the latest reply: two-step consent to the undo plan, and what the server said back. */
export function RetryControl({ threadId }: { threadId: string }) {
  const { thread, latestId, feedbackById } = useAssemble(threadId);
  const connected = useWsStore((s) => s.isConnected);
  const { retry, retrying, outcome } = useRetryReply({ threadId, onNotice: (text) => useSendNotice.getState().showNotice(text) });
  if (!latestId) return null;
  const feedback = feedbackById.get(latestId);
  const phase = thread.turn.phase;
  const busy = phase === "awaiting" || phase === "thinking" || phase === "speaking";
  return (
    <div className="assemble-retry">
      <RollbackNotice rollback={feedback?.rollback} busy={outcome?.kind === "busy"} />
      <RetryButton
        eligibility={feedback?.retry}
        isLatest
        connected={connected}
        busy={busy}
        retrying={retrying}
        onRetry={(plan) => retry(latestId, plan)}
      />
      {outcome && (
        <p role="status" className="assemble-outcome">
          <span className={outcome.kind === "busy" ? "muted" : "lbl hot"}>{outcome.detail}</span>
          {outcome.kind === "busy" && <Control onClick={() => send({ type: "command", name: "cancel", thread_id: threadId })}>Cancel</Control>}
        </p>
      )}
    </div>
  );
}
